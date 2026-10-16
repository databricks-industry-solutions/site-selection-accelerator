"""Cosine-similarity scoring between brand profile and candidate H3 cells."""

from __future__ import annotations

import h3
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from brand_search import h3_int_to_hex

_NEIGHBOR_DECAY = 0.5


def _locate_brand_cells(
    brand_locations: list[dict],
    resolution: int,
) -> list[int]:
    """Map brand lat/lon locations to H3 cell IDs.

    Parameters
    ----------
    brand_locations : list of dicts with keys ``lat`` and ``lon``.
    resolution : H3 resolution.

    Returns
    -------
    List of H3 cell IDs (BIGINT).
    """
    cells = []
    for loc in brand_locations:
        hex_str = h3.latlng_to_cell(loc["lat"], loc["lon"], resolution)
        cells.append(h3.str_to_int(hex_str))
    return cells


def compute_similarity(
    embeddings: pd.DataFrame,
    brand_locations: list[dict],
    resolution: int,
) -> tuple[pd.DataFrame, list[int]]:
    """Score every H3 cell by similarity to the brand profile.

    1. Identify H3 cells that contain the brand's existing locations.
    2. Expand each brand cell to its k=1 ring neighbors (that exist in
       the embedding index) with distance-weighted decay so the actual
       brand cell dominates while nearby context smooths sparse cells.
    3. Compute the weighted-mean embedding -> brand profile vector.
    4. Compute cosine similarity of every cell to the profile.
    5. Exclude cells that already contain a brand location.

    Returns
    -------
    scored : DataFrame with columns h3_cell, similarity, is_brand_cell
        sorted descending by similarity.
    brand_cells_in_emb : list of H3 cell IDs that form the brand profile.
    """
    brand_cells = _locate_brand_cells(brand_locations, resolution)
    brand_cells_in_emb = [c for c in brand_cells if c in embeddings.index]

    if not brand_cells_in_emb:
        raise ValueError(
            "None of the brand locations fall within the analysed H3 cells. "
            "This can happen when the brand-neighbourhood POI data is too "
            "sparse for the selected categories. Try selecting more POI "
            "categories or a coarser H3 resolution."
        )

    emb_index_set = set(embeddings.index)
    expanded: dict[int, float] = {}
    for c in brand_cells_in_emb:
        hex_str = h3.int_to_str(c)
        for neighbor in h3.grid_disk(hex_str, 1):
            n_int = h3.str_to_int(neighbor)
            if n_int in emb_index_set:
                dist = h3.grid_distance(hex_str, neighbor)
                w = 1.0 if dist == 0 else _NEIGHBOR_DECAY
                expanded[n_int] = max(expanded.get(n_int, 0.0), w)

    cells = list(expanded.keys())
    weights = np.array([expanded[c] for c in cells])
    brand_profile = np.average(
        embeddings.loc[cells].values, axis=0, weights=weights,
    ).reshape(1, -1)
    all_vectors = embeddings.values
    scores = cosine_similarity(brand_profile, all_vectors).flatten()

    result = pd.DataFrame(
        {
            "h3_cell": embeddings.index,
            "similarity": scores,
            "is_brand_cell": embeddings.index.isin(brand_cells),
        }
    )
    result = result.sort_values("similarity", ascending=False).reset_index(drop=True)
    return result, brand_cells_in_emb


def compute_opportunity_score(
    scored: pd.DataFrame,
    competition: pd.DataFrame,
    beta: float = 0.5,
) -> pd.DataFrame:
    """Apply competition adjustment to similarity scores.

    raw = similarity * (1 - beta * competition_score)
    opportunity_score = percentile_rank(raw)

    competition_score is normalised by the max of non-zero competitor
    counts, clipped to [0, 1]. The most saturated cell gets 1.0;
    cells with fewer competitors are penalised proportionally less.
    The final score is a percentile rank (0–1), keeping it bounded
    and distribution-aware regardless of beta direction.

    Beta range [-1, +1] controls the competition strategy:
      beta > 0 : penalise (avoid saturated areas)
      beta = 0 : ignore competition
      beta < 0 : boost  (mirror / co-locate near competition)

    Parameters
    ----------
    scored : DataFrame from compute_similarity.
    competition : DataFrame from find_competitors or named competitor lookup.
    beta : competition sensitivity (-1 = full mirror, 0 = ignore, +1 = full penalty).
    """
    scored = scored.copy()
    scored["h3_hex"] = scored["h3_cell"].apply(h3_int_to_hex)

    merged = scored.merge(
        competition[["h3_hex", "competitor_count", "top_competitors"]],
        on="h3_hex",
        how="left",
    )
    merged["competitor_count"] = merged["competitor_count"].fillna(0).astype(int)
    merged["top_competitors"] = merged["top_competitors"].fillna("")

    nonzero = competition.loc[competition["competitor_count"] > 0, "competitor_count"]
    cap = max(nonzero.max(), 1) if len(nonzero) > 0 else 1
    merged["competition_score"] = (merged["competitor_count"] / cap).clip(upper=1.0)

    raw = merged["similarity"] * (1 - beta * merged["competition_score"])
    merged["opportunity_score"] = raw.rank(pct=True)

    return merged.sort_values(
        "opportunity_score", ascending=False
    ).reset_index(drop=True)


def get_top_opportunities(
    scored: pd.DataFrame,
    top_n: int = 20,
) -> pd.DataFrame:
    """Return the top-N whitespace opportunities (excluding existing brand cells)."""
    sort_col = (
        "opportunity_score"
        if "opportunity_score" in scored.columns
        else "similarity"
    )

    return (
        scored[~scored["is_brand_cell"]]
        .sort_values(sort_col, ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


_EARTH_RADIUS_KM = 6371.0088


def compute_cannibalization(
    scored: pd.DataFrame,
    catchment_km: float = 1.5,
) -> pd.DataFrame:
    """Estimate how much of each candidate cell's trade area the brand already serves.

    Each existing brand cell (``is_brand_cell``) and each candidate is given a
    circular catchment of radius ``catchment_km``. A candidate's
    ``cannibalization_risk`` is the largest fraction of its catchment that
    overlaps an existing store's catchment (the circle-circle "lens" area over
    the circle area): 0 = entirely new territory, 1 = same trade area as an
    existing store. ``nearest_store_km`` is the distance to the closest one.

    Real-estate teams typically screen on exactly this — sales transfer from
    an existing store is the main reason a "high-similarity" site
    under-delivers — so it is reported alongside the opportunity score rather
    than folded into it, letting the user see the trade-off.
    """
    scored = scored.copy()
    own = scored.loc[scored["is_brand_cell"], "h3_cell"].astype("int64").unique()
    if len(own) == 0:
        scored["cannibalization_risk"] = 0.0
        scored["nearest_store_km"] = np.nan
        return scored

    def _latlon_rad(cells) -> np.ndarray:
        pts = [h3.cell_to_latlng(h3.int_to_str(int(c))) for c in cells]
        return np.radians(np.asarray(pts, dtype=float))

    cand = _latlon_rad(scored["h3_cell"].astype("int64"))
    stores = _latlon_rad(own)

    # Haversine distance matrix: candidates x existing stores (km).
    dlat = cand[:, None, 0] - stores[None, :, 0]
    dlon = cand[:, None, 1] - stores[None, :, 1]
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(cand[:, None, 0]) * np.cos(stores[None, :, 0]) * np.sin(dlon / 2) ** 2
    )
    dist = 2 * _EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    nearest = dist.min(axis=1)

    # Overlap fraction of two equal circles of radius r at centre distance d.
    r = float(catchment_km)
    d = np.minimum(nearest, 2 * r)
    lens = 2 * r**2 * np.arccos(d / (2 * r)) - (d / 2) * np.sqrt(np.maximum(4 * r**2 - d**2, 0.0))
    overlap = np.clip(lens / (np.pi * r**2), 0.0, 1.0)

    scored["nearest_store_km"] = np.round(nearest, 3)
    scored["cannibalization_risk"] = np.round(overlap, 4)
    return scored
