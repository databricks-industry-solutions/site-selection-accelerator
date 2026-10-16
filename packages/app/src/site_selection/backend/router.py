from __future__ import annotations

import json
import logging

import h3
import numpy as np
import pandas as pd
from fastapi import HTTPException, Query
from fastapi.responses import StreamingResponse

from .core import Dependencies, create_router
from .models import (
    AnalyzeRequest,
    AnalyzeResultOut,
    AnalysisSummary,
    AppConfigOut,
    AssetLink,
    AssetsOut,
    BrandLocationData,
    BrandPOIRow,
    BrandProfileOut,
    CategoryAvgItem,
    CategoryGroup,
    CellBreakdownRow,
    CompetitionInfo,
    CompetitorLocationData,
    CompetitorPOI,
    CellPOI,
    FingerprintRow,
    GenieDebugOut,
    HexagonData,
    HexagonDetailOut,
    PersistResultOut,
    ResolveAddressesRequest,
    ResolveAddressesResponse,
    ResolvedAddress,
    ResolvedPOI,
    ShortlistAddIn,
    ShortlistItemOut,
    ShortlistUpdateIn,
    VersionOut,
)
from . import cache
from .cache import PipelineResult

log = logging.getLogger(__name__)

router = create_router()


# -- Helpers ------------------------------------------------------------------

def _h3_int_to_hex(cell_id: int) -> str:
    if cell_id < 0:
        cell_id = cell_id + (1 << 64)
    return h3.int_to_str(cell_id)


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _h3_center(cell_id: int) -> tuple[float, float]:
    hex_str = _h3_int_to_hex(cell_id)
    return h3.cell_to_latlng(hex_str)


def _opt_round(value: object, ndigits: int) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), ndigits)


def _user_key(headers) -> str:
    """Identity the shortlist is scoped to (forwarded by Databricks Apps)."""
    return headers.user_email or headers.user_name or "local-dev"


def _score_to_rgba(score: float) -> list[int]:
    r = int(np.clip(score * 2, 0, 1) * 255)
    g = int(np.clip(2 - score * 2, 0, 1) * 150)
    b = int((1 - score) * 200)
    return [r, g, b, 140]


def _get_result(session_id: str) -> PipelineResult:
    result = cache.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return result


# -- Version ------------------------------------------------------------------

@router.get("/version", response_model=VersionOut, operation_id="version")
async def version():
    return VersionOut.from_metadata()



# -- Config -------------------------------------------------------------------

@router.get("/config", response_model=AppConfigOut, operation_id="getConfig")
async def get_config():
    try:
        from config import (
            CATEGORY_GROUPS,
            BUILDING_CATEGORY_GROUPS,
            H3_RESOLUTIONS,
            DEFAULT_H3_RESOLUTION,
        )
        return AppConfigOut(
            h3_resolutions=H3_RESOLUTIONS,
            default_resolution=DEFAULT_H3_RESOLUTION,
            category_groups=[
                CategoryGroup(name=k, categories=v) for k, v in CATEGORY_GROUPS.items()
            ],
            building_category_groups=[
                CategoryGroup(name=k, categories=v) for k, v in BUILDING_CATEGORY_GROUPS.items()
            ],
        )
    except Exception as e:
        log.exception("config endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Countries / Cities -------------------------------------------------------

@router.get("/countries", response_model=list[str], operation_id="listCountries")
async def list_countries():
    try:
        from pipeline import get_countries
        return get_countries()
    except Exception as e:
        log.exception("countries endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cities", response_model=list[str], operation_id="listCities")
async def list_cities(country: str = Query(...)):
    try:
        from pipeline import get_cities
        return get_cities(country)
    except Exception as e:
        log.exception("cities endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Address Resolution --------------------------------------------------------

@router.post(
    "/resolve-addresses",
    response_model=ResolveAddressesResponse,
    operation_id="resolveAddresses",
)
async def resolve_addresses(req: ResolveAddressesRequest):
    """Geocode addresses and return candidate POIs at each location.

    The frontend uses this to let the user disambiguate which POI(s)
    they actually mean before running the full analysis.
    """
    try:
        from geopy.geocoders import Nominatim
        from db import execute_query
        import config as cfg

        geocoder = Nominatim(user_agent="site-selection-accelerator")
        results: list[ResolvedAddress] = []

        for line in req.addresses.strip().splitlines():
            addr = line.strip()
            if not addr:
                continue
            try:
                geo_result = geocoder.geocode(addr, timeout=10)
            except Exception as geo_err:
                log.warning("Geocoding failed for '%s': %s", addr, geo_err)
                continue
            if not geo_result:
                continue

            lat, lon = geo_result.latitude, geo_result.longitude
            source_parts = [p.strip() for p in addr.split(",") if p.strip()]
            source_line = source_parts[0] if source_parts else addr
            escaped = source_line.replace("'", "''")

            try:
                poi_df = execute_query(f"""
                    SELECT p.poi_id, p.poi_primary_name, p.basic_category,
                           p.brand_name_primary
                    FROM {cfg.GOLD_PLACES_ENRICHED} p
                    WHERE p.lon IS NOT NULL AND p.lat IS NOT NULL
                      AND lower(trim(p.address_line)) = lower(trim('{escaped}'))
                """)
            except Exception:
                poi_df = pd.DataFrame()

            pois = []
            for _, row in poi_df.iterrows():
                name = str(row.get("poi_primary_name", "") or "")
                brand = str(row.get("brand_name_primary", "") or "")
                pois.append(ResolvedPOI(
                    poi_id=str(row["poi_id"]),
                    name=name or brand or "Unknown",
                    brand=brand,
                    category=str(row.get("basic_category", "") or ""),
                ))

            results.append(ResolvedAddress(address=addr, lat=lat, lon=lon, pois=pois))

        return ResolveAddressesResponse(results=results)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("resolve-addresses endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Analyze (SSE) ------------------------------------------------------------

@router.post("/analyze", operation_id="analyze")
async def analyze(req: AnalyzeRequest, headers: Dependencies.Headers) -> StreamingResponse:
    """Run the full site-selection pipeline, streaming progress via SSE.

    Final event contains the session_id for retrieving results.
    """
    def event_stream():
        try:
            yield _sse({"type": "progress", "step": "starting", "pct": 0})

            from pipeline import (
                build_count_vectors,
                get_buildings_around_points,
                get_buildings_with_h3,
                get_city_polygon,
                get_nearest_address_per_cell,
                get_pois_around_points,
                get_pois_with_h3,
                tessellate_city,
            )
            from embeddings import load_hex2vec, normalise_buildings, run_embedding_pipeline
            from similarity import (
                compute_cannibalization,
                compute_opportunity_score,
                compute_similarity,
            )
            from explainability import build_brand_profile, tooltip_snippet
            from brand_search import (
                discover_brand_locations,
                find_competitors_in_similar_cells,
                infer_location_categories,
            )
            from config import HEX2VEC_VOLUME_PATH, ALL_BUILDING_CATEGORIES

            # Load pretrained model
            yield _sse({"type": "progress", "step": "loading_model", "pct": 5})
            try:
                pretrained, pretrained_meta = load_hex2vec(HEX2VEC_VOLUME_PATH)
            except Exception:
                pretrained, pretrained_meta = None, None

            # Radiance: check cache, submit serverless job on miss
            radiance_df = None
            radiance_run_id = None
            if req.include_radiance:
                from radiance import (
                    check_radiance_job,
                    get_radiance_for_city,
                    submit_radiance_job,
                )

                radiance_df = get_radiance_for_city(req.country, req.city, req.resolution)
                if radiance_df is None:
                    try:
                        radiance_run_id = submit_radiance_job(
                            req.country, req.city, req.resolution,
                        )
                        if radiance_run_id:
                            log.info("Submitted radiance job run_id=%s", radiance_run_id)
                    except Exception as e:
                        log.debug("Could not submit radiance job: %s", e)

            # Resolve brand locations
            yield _sse({"type": "progress", "step": "resolving_brand", "pct": 10})
            brand_pois_df = None
            analysis_mode = "brand"
            if req.brand_input.mode == "brand_name":
                brand_locations, _, brand_pois_df = discover_brand_locations(
                    req.brand_input.value, req.resolution,
                    country=req.country, city=req.city,
                )
                if not brand_locations:
                    yield _sse({"type": "error", "message": f"No locations found for '{req.brand_input.value}'"})
                    return
            elif req.brand_input.mode == "map_selection":
                analysis_mode = "location"
                if not req.brand_input.geojson:
                    yield _sse({"type": "error", "message": "No map features provided"})
                    return
                brand_locations = _parse_map_selection(req.brand_input.geojson, req.resolution)
                if not brand_locations:
                    yield _sse({"type": "error", "message": "No valid locations from map selection"})
                    return
                if req.enable_competition and req.beta != 0:
                    brand_pois_df = infer_location_categories(
                        brand_locations, req.resolution, req.country, req.city,
                        restrict_to_target_city=False,
                    )
            else:
                analysis_mode = "location"
                brand_locations = _parse_locations(req.brand_input.value, req.brand_input.mode)
                if not brand_locations:
                    yield _sse({"type": "error", "message": "No valid locations parsed"})
                    return
                if req.enable_competition and req.beta != 0:
                    brand_pois_df = infer_location_categories(
                        brand_locations, req.resolution, req.country, req.city,
                        restrict_to_target_city=False,
                    )
                    if (
                        req.brand_input.selected_poi_ids
                        and brand_pois_df is not None
                        and not brand_pois_df.empty
                        and "poi_id" in brand_pois_df.columns
                    ):
                        brand_pois_df = brand_pois_df[
                            brand_pois_df["poi_id"].astype(str).isin(req.brand_input.selected_poi_ids)
                        ]

            # For address/latlng cross-region: find existing brand in target city
            existing_target_locs: list[dict] = []
            if analysis_mode == "location" and brand_pois_df is not None and not brand_pois_df.empty:
                dominant_brand = _extract_dominant_brand(brand_pois_df)
                if not dominant_brand:
                    dominant_brand = _extract_brand_from_input(
                        brand_pois_df, req.brand_input.value,
                    )
                if dominant_brand:
                    try:
                        target_locs, _, _ = discover_brand_locations(
                            dominant_brand, req.resolution,
                            country=req.country, city=req.city,
                        )
                        existing_target_locs = target_locs or []
                        log.info(
                            "Cross-region: found %d existing '%s' locations in %s, %s",
                            len(existing_target_locs), dominant_brand, req.city, req.country,
                        )
                    except Exception as e:
                        log.warning("Cross-region brand lookup failed for '%s': %s", dominant_brand, e)

            # Tessellate
            yield _sse({"type": "progress", "step": "tessellating", "pct": 15})
            city_h3_cells_df = tessellate_city(req.country, req.city, req.resolution)
            city_geo = get_city_polygon(req.country, req.city)
            _has_poly = city_geo.get("has_polygon")
            if isinstance(_has_poly, str):
                _has_poly = _has_poly.lower() == "true"
            city_polygon_wkt = city_geo["geom_wkt"] if _has_poly else None

            city_cell_set = set(city_h3_cells_df["h3_cell"].tolist())

            # Detect brand outside city
            brand_outside = []
            for loc in brand_locations:
                hex_str = h3.latlng_to_cell(loc["lat"], loc["lon"], req.resolution)
                if h3.str_to_int(hex_str) not in city_cell_set:
                    brand_outside.append(loc)

            h3_cells_df = city_h3_cells_df
            if brand_outside:
                yield _sse({"type": "progress", "step": "fetching_brand_context", "pct": 18})
                brand_ctx_cells, brand_ctx_pois = get_pois_around_points(
                    brand_outside, req.resolution, req.categories, k_ring=2,
                )
                new_cells = brand_ctx_cells[~brand_ctx_cells["h3_cell"].isin(city_cell_set)]
                h3_cells_df = pd.concat([city_h3_cells_df, new_cells], ignore_index=True)
            else:
                brand_ctx_pois = pd.DataFrame()

            # Query POIs
            yield _sse({"type": "progress", "step": "querying_pois", "pct": 20})
            city_pois_df = get_pois_with_h3(req.country, req.city, req.resolution, req.categories)
            if brand_outside and not brand_ctx_pois.empty:
                pois_df = pd.concat([city_pois_df, brand_ctx_pois], ignore_index=True).drop_duplicates(subset=["poi_id"])
            else:
                pois_df = city_pois_df

            if pois_df.empty:
                yield _sse({"type": "error", "message": "No POIs found for selected categories"})
                return

            # Buildings
            buildings_features = pd.DataFrame()
            if req.include_buildings:
                yield _sse({"type": "progress", "step": "querying_buildings", "pct": 32})
                city_bldg_df = get_buildings_with_h3(req.country, req.city, req.resolution)
                if brand_outside:
                    brand_ctx_bldg = get_buildings_around_points(brand_outside, req.resolution, k_ring=2)
                    if not brand_ctx_bldg.empty:
                        city_bldg_df = pd.concat([city_bldg_df, brand_ctx_bldg], ignore_index=True).drop_duplicates(subset=["building_id"])
                if not city_bldg_df.empty:
                    buildings_features = normalise_buildings(city_bldg_df)

            poi_features = pois_df[["poi_id", "category", "lon", "lat", "h3_cell"]].copy()
            poi_features = poi_features.rename(columns={"poi_id": "feature_id"})
            if not buildings_features.empty:
                features_df = pd.concat([poi_features, buildings_features], ignore_index=True)
            else:
                features_df = poi_features

            all_cats = list(req.categories)
            if req.include_buildings and not buildings_features.empty:
                present_bldg_cats = sorted(buildings_features["category"].unique())
                all_cats = all_cats + present_bldg_cats

            yield _sse({"type": "progress", "step": "building_vectors", "pct": 40})
            count_vectors = build_count_vectors(features_df)

            # Embeddings
            use_pretrained = (
                pretrained is not None
                and pretrained_meta is not None
                and pretrained_meta.get("resolution") == req.resolution
            )

            yield _sse({"type": "progress", "step": "generating_embeddings", "pct": 50})
            if use_pretrained and pretrained_meta is not None:
                training_cats = pretrained_meta["categories"]
                embeddings = run_embedding_pipeline(
                    h3_cells_df, features_df, all_cats,
                    pretrained_embedder=pretrained,
                    training_categories=training_cats,
                )
            else:
                embeddings = run_embedding_pipeline(h3_cells_df, features_df, all_cats)

            # Similarity
            yield _sse({"type": "progress", "step": "computing_similarity", "pct": 80})
            scored, brand_cells_in_emb = compute_similarity(embeddings, brand_locations, req.resolution)

            brand_profile = build_brand_profile(count_vectors, brand_cells_in_emb)
            brand_avg = brand_profile["avg"]

            scored = scored[scored["h3_cell"].isin(city_cell_set)].reset_index(drop=True)
            s_min, s_max = scored["similarity"].min(), scored["similarity"].max()
            if s_max - s_min > 0:
                scored["similarity"] = (scored["similarity"] - s_min) / (s_max - s_min)
            else:
                scored["similarity"] = np.zeros(len(scored))

            # POI density for display (not used in scoring)
            poi_totals = count_vectors.sum(axis=1).rename("poi_density")
            scored = scored.merge(poi_totals, left_on="h3_cell", right_index=True, how="left")
            scored["poi_density"] = scored["poi_density"].fillna(0).astype(int)

            # Radiance: poll gold_radiance table until data appears
            if radiance_df is None and radiance_run_id is not None:
                import time as _time

                yield _sse({"type": "progress", "step": "computing_radiance", "pct": 82})
                max_wait_s = 300
                poll_interval_s = 1
                keepalive_interval_s = 15
                elapsed = 0.0
                try:
                    while elapsed < max_wait_s:
                        radiance_df = get_radiance_for_city(
                            req.country, req.city, req.resolution,
                        )
                        if radiance_df is not None:
                            log.info(
                                "Radiance data available (%.0fs), %d cells",
                                elapsed, len(radiance_df),
                            )
                            break
                        status = check_radiance_job(radiance_run_id)
                        if status == "FAILED":
                            log.warning("Radiance job failed after %.0fs", elapsed)
                            break
                        _time.sleep(poll_interval_s)
                        elapsed += poll_interval_s
                        if elapsed % keepalive_interval_s == 0:
                            pct = min(82 + int(elapsed / max_wait_s * 8), 89)
                            yield _sse({"type": "progress", "step": "computing_radiance", "pct": pct})
                    else:
                        log.warning("Radiance wait timed out after %ds", max_wait_s)
                except Exception as e:
                    log.debug("Radiance poll failed: %s", e)

            if radiance_df is not None:
                scored = scored.merge(
                    radiance_df[["h3_cell", "radiance"]],
                    on="h3_cell", how="left",
                )
                log.info("Radiance merged: %d cells with values", scored["radiance"].notna().sum())

            # Competition / Saturation
            competitor_pois = None
            named_competitor_found = False
            if req.enable_competition and req.beta != 0:
                yield _sse({"type": "progress", "step": "finding_competitors", "pct": 85})

                if req.competitor_brand.strip():
                    competition, competitor_pois = _find_named_competitor(
                        req.competitor_brand, scored, req.resolution,
                        req.country, req.city,
                    )
                    if competitor_pois is not None and not competitor_pois.empty:
                        named_competitor_found = True
                    else:
                        log.warning(
                            "Named competitor '%s' returned no results, "
                            "falling back to category-based competition",
                            req.competitor_brand,
                        )

                if not named_competitor_found and brand_pois_df is not None and not brand_pois_df.empty:
                    competition, competitor_pois = find_competitors_in_similar_cells(
                        scored, brand_pois=brand_pois_df,
                        brand_query=req.brand_input.value if req.brand_input.mode == "brand_name" else "",
                        min_similarity=0.5, country=req.country, city=req.city,
                        resolution=req.resolution,
                    )

                if competitor_pois is not None and not competitor_pois.empty:
                    scored = compute_opportunity_score(
                        scored, competition, beta=req.beta,
                    )

            address_lookup = get_nearest_address_per_cell(pois_df)

            # Mark existing target brand locations in scored so they are excluded
            if existing_target_locs:
                target_cell_ints = set()
                for loc in existing_target_locs:
                    hex_str = h3.latlng_to_cell(loc["lat"], loc["lon"], req.resolution)
                    target_cell_ints.add(h3.str_to_int(hex_str))
                scored.loc[scored["h3_cell"].isin(target_cell_ints), "is_brand_cell"] = True

            # Cannibalization: trade-area overlap with the brand's own stores
            scored = compute_cannibalization(scored, catchment_km=req.catchment_km)

            # Cache results (memory) and write through to Lakebase
            yield _sse({"type": "progress", "step": "caching_results", "pct": 95})
            pr = PipelineResult(
                count_vectors=count_vectors,
                brand_avg=brand_avg,
                brand_profile=brand_profile,
                scored=scored,
                address_lookup=address_lookup,
                brand_locations=brand_locations,
                city_h3_cells_df=city_h3_cells_df,
                pois_df=pois_df,
                competitor_pois=competitor_pois,
                city_polygon_wkt=city_polygon_wkt,
                analysis_mode=analysis_mode,
                brand_pois=brand_pois_df,
            )
            session_id = cache.save(pr)
            try:
                import lakebase

                lakebase.save_session(
                    session_id, pr,
                    created_by=_user_key(headers),
                    brand=req.brand_input.value if req.brand_input.mode == "brand_name" else "",
                    country=req.country, city=req.city, resolution=req.resolution,
                )
            except Exception:
                log.exception("Lakebase write-through failed; session %s is memory-only", session_id)

            # Build hexagon data for the response
            hexagons = _build_hexagon_list(scored, address_lookup, count_vectors, brand_avg)
            brand_locs = _build_brand_location_list(brand_locations, req.resolution, address_lookup)

            existing_target_brand_locs: list[BrandLocationData] = []
            if existing_target_locs:
                existing_target_brand_locs = _build_brand_location_list(
                    existing_target_locs, req.resolution, address_lookup,
                )
                for loc in existing_target_brand_locs:
                    loc.is_source = False

            city_polygon_geojson = None
            if city_polygon_wkt:
                city_polygon_geojson = _wkt_to_geojson(city_polygon_wkt)

            comp_loc_list: list[CompetitorLocationData] = []
            if named_competitor_found and competitor_pois is not None and not competitor_pois.empty:
                comp_loc_list = _build_competitor_location_list(
                    competitor_pois, req.resolution,
                )

            result_data = AnalyzeResultOut(
                session_id=session_id,
                hexagons=hexagons,
                brand_locations=brand_locs,
                existing_target_locations=existing_target_brand_locs,
                competitor_locations=comp_loc_list,
                city_polygon_geojson=city_polygon_geojson,
                has_competition="opportunity_score" in scored.columns,
                competitor_brand=req.competitor_brand.strip() if named_competitor_found else "",
                analysis_mode=analysis_mode,
                center_lat=float(city_h3_cells_df["center_lat"].mean()),
                center_lon=float(city_h3_cells_df["center_lon"].mean()),
            )

            yield _sse({"type": "progress", "step": "done", "pct": 100})
            yield _sse({"type": "result", "data": result_data.model_dump()})

        except Exception as exc:
            log.exception("Pipeline error")
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- Results ------------------------------------------------------------------

@router.get("/results/{session_id}", response_model=AnalyzeResultOut, operation_id="getResults")
async def get_results(session_id: str):
    try:
        pr = _get_result(session_id)
        hexagons = _build_hexagon_list(pr.scored, pr.address_lookup, pr.count_vectors, pr.brand_avg)

        if pr.scored.empty:
            raise HTTPException(status_code=404, detail="No scored hexagons in this session")
        resolution = h3.get_resolution(_h3_int_to_hex(pr.scored["h3_cell"].iloc[0]))
        brand_locs = _build_brand_location_list(pr.brand_locations, resolution, pr.address_lookup)
        city_polygon_geojson = _wkt_to_geojson(pr.city_polygon_wkt) if pr.city_polygon_wkt else None

        return AnalyzeResultOut(
            session_id=session_id,
            hexagons=hexagons,
            brand_locations=brand_locs,
            city_polygon_geojson=city_polygon_geojson,
            has_competition="opportunity_score" in pr.scored.columns,
            analysis_mode=getattr(pr, "analysis_mode", "brand"),
            center_lat=float(pr.city_h3_cells_df["center_lat"].mean()),
            center_lon=float(pr.city_h3_cells_df["center_lon"].mean()),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("get_results endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Brand Profile ------------------------------------------------------------

@router.get(
    "/results/{session_id}/brand-profile",
    response_model=BrandProfileOut,
    operation_id="getBrandProfile",
)
async def get_brand_profile(session_id: str):
    try:
        pr = _get_result(session_id)
        from config import ALL_BUILDING_CATEGORIES, ALL_FEATURE_GROUPS

        brand_avg = pr.brand_avg
        avg_nonzero = brand_avg[brand_avg > 0].sort_values(ascending=False)

        avg_items: list[CategoryAvgItem] = []
        if not avg_nonzero.empty:
            bldg_set = set(ALL_BUILDING_CATEGORIES)
            group_lookup = {}
            for grp, cats in ALL_FEATURE_GROUPS.items():
                for c in cats:
                    group_lookup[c] = grp

            avg_df = avg_nonzero.reset_index()
            avg_df.columns = ["category_raw", "avg_count"]
            avg_df["feature_type"] = avg_df["category_raw"].apply(
                lambda c: "Building" if c in bldg_set else "POI"
            )
            for ft in ("POI", "Building"):
                mask = avg_df["feature_type"] == ft
                ft_total = avg_df.loc[mask, "avg_count"].sum()
                if ft_total > 0:
                    avg_df.loc[mask, "pct"] = (avg_df.loc[mask, "avg_count"] / ft_total * 100).round(1)
                else:
                    avg_df.loc[mask, "pct"] = 0.0

            for _, row in avg_df.iterrows():
                cat_display = row["category_raw"].replace("_", " ").title()
                avg_items.append(CategoryAvgItem(
                    category=cat_display,
                    avg_count=round(float(row["avg_count"]), 2),
                    pct_within_type=float(row.get("pct", 0)),
                    feature_type=row["feature_type"],
                    group=group_lookup.get(row["category_raw"], "Other"),
                ))

        cell_rows: list[CellBreakdownRow] = []
        brand_cells_df = pr.brand_profile["cells"]
        if not brand_cells_df.empty:
            for cell_id, row in brand_cells_df.iterrows():
                loc_label = pr.address_lookup.get(cell_id, _h3_int_to_hex(cell_id))
                for cat in brand_cells_df.columns:
                    val = float(row[cat])
                    if val > 0:
                        cell_rows.append(CellBreakdownRow(
                            location=loc_label,
                            category=cat.replace("_", " ").title(),
                            count=val,
                        ))

        return BrandProfileOut(avg_profile=avg_items, cell_breakdown=cell_rows)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("brand-profile endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Hexagon Detail -----------------------------------------------------------

@router.get(
    "/results/{session_id}/hexagon/{hex_id}",
    response_model=HexagonDetailOut,
    operation_id="getHexagonDetail",
)
async def get_hexagon_detail(session_id: str, hex_id: str):
    try:
        pr = _get_result(session_id)
        h3_cell = h3.str_to_int(hex_id)
        from explainability import (
            build_fingerprint_df,
            explain_competition,
            summarise_fingerprint,
        )

        fingerprint_df = build_fingerprint_df(h3_cell, pr.count_vectors, pr.brand_avg)
        try:
            summary = summarise_fingerprint(fingerprint_df)
        except Exception as exc:
            log.warning("summarise_fingerprint error: %s", exc)
            summary = ""
        fp_rows: list[FingerprintRow] = []
        if not fingerprint_df.empty:
            for _, row in fingerprint_df.iterrows():
                fp_rows.append(FingerprintRow(
                    category=row["Category"],
                    group=row["Group"],
                    feature_type=row["Feature Type"],
                    this_location=float(row["This Location"]),
                    brand_average=float(row["Brand Average"]),
                    this_location_pct=float(row["This Location (%)"]),
                    brand_average_pct=float(row["Brand Average (%)"]),
                ))

        comp_info = None
        if "opportunity_score" in pr.scored.columns:
            comp_raw = explain_competition(h3_cell, pr.scored)
            if comp_raw:
                comp_info = CompetitionInfo(**comp_raw)

        hex_id = _h3_int_to_hex(h3_cell)
        address = pr.address_lookup.get(h3_cell, "")

        cell_competitor_pois: list[CompetitorPOI] = []
        if pr.competitor_pois is not None and not pr.competitor_pois.empty:
            cell_comps = pr.competitor_pois[pr.competitor_pois["h3_hex"] == hex_id]
            for _, cr in cell_comps.iterrows():
                cell_competitor_pois.append(CompetitorPOI(
                    name=_clean_text(cr.get("poi_primary_name")),
                    category=_clean_text(cr.get("basic_category", cr.get("poi_primary_category", ""))),
                    brand=_clean_text(cr.get("brand_name_primary")),
                    address=_clean_text(cr.get("address_line")),
                ))

        cell_pois: list[CellPOI] = []
        cell_pois_title = ""
        if pr.brand_pois is not None and not pr.brand_pois.empty:
            bp = pr.brand_pois.copy()
            if "h3_cell" not in bp.columns and {"lon", "lat"}.issubset(bp.columns):
                resolution = h3.get_resolution(hex_id)
                bp["h3_cell"] = bp.apply(
                    lambda r: h3.latlng_to_cell(float(r["lat"]), float(r["lon"]), resolution)
                    if pd.notna(r.get("lat")) and pd.notna(r.get("lon")) else "",
                    axis=1,
                )

            cell_matches = bp[bp["h3_cell"].astype(str) == hex_id]
            if not cell_matches.empty:
                cell_pois_title = "Existing locations in this cell"

                for _, row in cell_matches.iterrows():
                    name = _clean_text(row.get("poi_primary_name"))
                    if not name:
                        continue
                    cell_pois.append(CellPOI(
                        name=name,
                        category=_clean_text(row.get("basic_category", row.get("poi_primary_category", ""))),
                        brand=_clean_text(row.get("brand_name_primary")),
                        address=_clean_text(row.get("address_line")),
                    ))

        row_match = pr.scored[pr.scored["h3_cell"] == h3_cell]
        similarity = float(row_match.iloc[0]["similarity"]) if not row_match.empty else 0.0
        opp_score = None
        poi_density_val = 0
        cannibalization = None
        nearest_store = None
        if not row_match.empty:
            r = row_match.iloc[0]
            if "opportunity_score" in r.index:
                opp_score = float(r["opportunity_score"])
            if "poi_density" in r.index:
                poi_density_val = int(r["poi_density"])
            cannibalization = _opt_round(r.get("cannibalization_risk"), 4)
            nearest_store = _opt_round(r.get("nearest_store_km"), 3)

        return HexagonDetailOut(
            h3_cell=h3_cell,
            hex_id=hex_id,
            address=address,
            similarity=similarity,
            opportunity_score=opp_score,
            poi_density=poi_density_val,
            cannibalization_risk=cannibalization,
            nearest_store_km=nearest_store,
            explanation_summary=summary,
            competition=comp_info,
            competitor_pois=cell_competitor_pois,
            cell_pois_title=cell_pois_title,
            cell_pois=cell_pois,
            fingerprint=fp_rows,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("hexagon-detail endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Shortlist (Lakebase) -----------------------------------------------------

def _require_lakebase():
    import lakebase

    if not lakebase.is_enabled():
        raise HTTPException(
            status_code=503,
            detail="Shortlist needs the Lakebase database resource attached to the app",
        )
    return lakebase


@router.get("/shortlist", response_model=list[ShortlistItemOut], operation_id="listShortlist")
async def list_shortlist(headers: Dependencies.Headers, session_id: str | None = Query(None)):
    lb = _require_lakebase()
    return lb.list_shortlist(_user_key(headers), session_id=session_id)


@router.post("/shortlist", response_model=ShortlistItemOut, operation_id="addToShortlist")
async def add_to_shortlist(req: ShortlistAddIn, headers: Dependencies.Headers):
    lb = _require_lakebase()
    try:
        return lb.add_to_shortlist(_user_key(headers), req.session_id, req.hex_id, req.note)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/shortlist/{item_id}", response_model=ShortlistItemOut, operation_id="updateShortlistItem")
async def update_shortlist_item(item_id: int, req: ShortlistUpdateIn, headers: Dependencies.Headers):
    lb = _require_lakebase()
    item = lb.update_shortlist(_user_key(headers), item_id, status=req.status, note=req.note)
    if item is None:
        raise HTTPException(status_code=404, detail="Shortlist item not found")
    return item


@router.delete("/shortlist/{item_id}", operation_id="removeShortlistItem")
async def remove_shortlist_item(item_id: int, headers: Dependencies.Headers) -> dict:
    lb = _require_lakebase()
    if not lb.remove_from_shortlist(_user_key(headers), item_id):
        raise HTTPException(status_code=404, detail="Shortlist item not found")
    return {"deleted": item_id}


# -- Genie Debug (brand POIs + competitor summary) ----------------------------

@router.get(
    "/results/{session_id}/debug",
    response_model=GenieDebugOut,
    operation_id="getGenieDebug",
)
async def get_genie_debug(session_id: str):
    try:
        pr = _get_result(session_id)

        brand_rows: list[BrandPOIRow] = []
        if pr.brand_pois is not None and not pr.brand_pois.empty:
            for _, row in pr.brand_pois.iterrows():
                brand_rows.append(BrandPOIRow(
                    name=str(row.get("poi_primary_name", "")),
                    category=str(row.get("basic_category", row.get("poi_primary_category", ""))),
                    brand=str(row.get("brand_name_primary", "") or ""),
                    lat=float(row["lat"]) if pd.notna(row.get("lat")) else None,
                    lon=float(row["lon"]) if pd.notna(row.get("lon")) else None,
                    h3_cell=str(row.get("h3_cell", "")),
                ))

        competitor_total = 0
        if pr.competitor_pois is not None and not pr.competitor_pois.empty:
            competitor_total = len(pr.competitor_pois)

        return GenieDebugOut(
            brand_pois=brand_rows,
            total_brand_pois=len(brand_rows),
            competitor_pois_total=competitor_total,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("genie-debug endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Persist Analysis ---------------------------------------------------------

@router.post(
    "/results/{session_id}/persist",
    response_model=PersistResultOut,
    operation_id="persistAnalysis",
)
async def persist_analysis(session_id: str):
    """Persist the in-memory analysis results to Delta tables."""
    try:
        pr = _get_result(session_id)
        from persist import persist_analysis as do_persist

        city_polygon_geojson = _wkt_to_geojson(pr.city_polygon_wkt) if pr.city_polygon_wkt else None

        if pr.scored.empty:
            raise HTTPException(status_code=404, detail="No scored hexagons to persist")
        resolution = h3.get_resolution(_h3_int_to_hex(pr.scored["h3_cell"].iloc[0]))
        request_data = {
            "brand_input_mode": "",
            "brand_input_value": "",
            "country": "",
            "city": "",
            "resolution": resolution,
            "categories": [],
            "enable_competition": "opportunity_score" in pr.scored.columns,
            "beta": 1.0,
            "include_buildings": True,
        }

        center_lat = float(pr.city_h3_cells_df["center_lat"].mean())
        center_lon = float(pr.city_h3_cells_df["center_lon"].mean())

        result = do_persist(
            session_id=session_id,
            request_data=request_data,
            pipeline_result=pr,
            city_polygon_geojson=city_polygon_geojson,
            center_lat=center_lat,
            center_lon=center_lon,
        )
        pr.compact()
        return PersistResultOut(
            analysis_id=result["analysis_id"],
            tables_written=result["tables_written"],
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("persist endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/results/{session_id}/persist-with-context",
    response_model=PersistResultOut,
    operation_id="persistAnalysisWithContext",
)
async def persist_analysis_with_context(session_id: str, req: AnalyzeRequest):
    """Persist analysis results to Delta, using the original request for metadata."""
    try:
        pr = _get_result(session_id)
        from persist import persist_analysis as do_persist

        city_polygon_geojson = _wkt_to_geojson(pr.city_polygon_wkt) if pr.city_polygon_wkt else None
        center_lat = float(pr.city_h3_cells_df["center_lat"].mean())
        center_lon = float(pr.city_h3_cells_df["center_lon"].mean())

        request_data = {
            "brand_input_mode": req.brand_input.mode,
            "brand_input_value": req.brand_input.value,
            "country": req.country,
            "city": req.city,
            "resolution": req.resolution,
            "categories": req.categories,
            "enable_competition": req.enable_competition,
            "beta": req.beta,
            "include_buildings": req.include_buildings,
        }

        result = do_persist(
            session_id=session_id,
            request_data=request_data,
            pipeline_result=pr,
            city_polygon_geojson=city_polygon_geojson,
            center_lat=center_lat,
            center_lon=center_lon,
        )
        pr.compact()
        return PersistResultOut(
            analysis_id=result["analysis_id"],
            tables_written=result["tables_written"],
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("persist-with-context endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Assets -------------------------------------------------------------------

@router.get("/assets", response_model=AssetsOut, operation_id="getAssets")
async def get_assets():
    """Return links to all Databricks assets produced by this accelerator."""
    try:
        import os
        from config import (
            GENIE_SPACE_ID,
            GOLD_CITIES_TABLE,
            GOLD_PLACES_TABLE,
            GOLD_PLACES_ENRICHED,
            GOLD_BUILDINGS_TABLE,
            ANALYSES_TABLE,
            ANALYSIS_BRAND_PROFILES_TABLE,
            ANALYSIS_HEXAGONS_TABLE,
            ANALYSIS_FINGERPRINTS_TABLE,
            ANALYSIS_COMPETITORS_TABLE,
            HEX2VEC_VOLUME_PATH,
        )
        from persist import list_analyses

        host = os.getenv("DATABRICKS_HOST", "")
        if host and not host.startswith("https://"):
            host = f"https://{host}"
        host = host.rstrip("/")

        links: list[AssetLink] = []

        if host:
            links.append(AssetLink(name="Databricks Workspace", url=host, asset_type="workspace"))

        if GENIE_SPACE_ID:
            links.append(AssetLink(
                name="Genie Space (Brand Explorer)",
                url=f"{host}/genie/rooms/{GENIE_SPACE_ID}" if host else "",
                asset_type="genie",
            ))

        etl_job_id = os.getenv("ETL_JOB_ID", "")
        if etl_job_id and host:
            links.append(AssetLink(
                name="Geospatial ETL Job",
                url=f"{host}/jobs/{etl_job_id}",
                asset_type="job",
            ))

        radiance_job_id = os.getenv("RADIANCE_JOB_ID", "")
        if radiance_job_id and host:
            links.append(AssetLink(
                name="On-Demand Radiance Job",
                url=f"{host}/jobs/{radiance_job_id}",
                asset_type="job",
            ))

        links.append(AssetLink(
            name="Hex2Vec Pretrained Model",
            url=f"{host}/explore/data/volumes{HEX2VEC_VOLUME_PATH}" if host else HEX2VEC_VOLUME_PATH,
            asset_type="volume",
        ))

        gold_tables = [
            ("Gold Cities", GOLD_CITIES_TABLE),
            ("Gold Places", GOLD_PLACES_TABLE),
            ("Gold Places Enriched", GOLD_PLACES_ENRICHED),
            ("Gold Buildings", GOLD_BUILDINGS_TABLE),
        ]
        analysis_tables = [
            ("Analyses Registry", ANALYSES_TABLE),
            ("Analysis Brand Profiles", ANALYSIS_BRAND_PROFILES_TABLE),
            ("Analysis Hexagons", ANALYSIS_HEXAGONS_TABLE),
            ("Analysis Fingerprints", ANALYSIS_FINGERPRINTS_TABLE),
            ("Analysis Competitors", ANALYSIS_COMPETITORS_TABLE),
        ]
        for label, fqn in gold_tables + analysis_tables:
            parts = fqn.split(".")
            table_url = f"{host}/explore/data/{'/'.join(parts)}" if host and len(parts) == 3 else ""
            links.append(AssetLink(name=label, url=table_url, asset_type="table"))

        recent = list_analyses(limit=10)
        analyses = [
            AnalysisSummary(
                analysis_id=str(r.get("analysis_id", "")),
                brand_input_value=str(r.get("brand_input_value", "")),
                city=str(r.get("city", "")),
                country=str(r.get("country", "")),
                created_at=str(r.get("created_at", "")),
            )
            for r in recent
        ]

        return AssetsOut(
            workspace_url=host,
            links=links,
            recent_analyses=analyses,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("assets endpoint failed")
        raise HTTPException(status_code=500, detail=str(e))


# -- Internal helpers ---------------------------------------------------------

def _extract_dominant_brand(brand_pois_df: pd.DataFrame) -> str | None:
    """Return the most common brand name from inferred POIs, or None.

    For mixed-address results where many POIs share an address, we look
    at poi_primary_name as a fallback when brand_name_primary is sparse.
    Uses a relaxed threshold: the top brand just needs >= 2 occurrences
    OR be the single most common name.
    """
    for col in ("brand_name_primary", "poi_primary_name"):
        if col not in brand_pois_df.columns:
            continue
        names = brand_pois_df[col].dropna().astype(str).str.strip()
        names = names[names.str.len() > 0]
        if names.empty:
            continue
        counts = names.value_counts()
        top_name = counts.index[0]
        top_count = counts.iloc[0]
        log.info(
            "Brand extraction (%s): top='%s' count=%d total=%d",
            col, top_name, top_count, len(brand_pois_df),
        )
        if top_count >= 2 or len(brand_pois_df) == 1:
            return top_name
    return None


def _extract_brand_from_input(
    brand_pois_df: pd.DataFrame, raw_input: str,
) -> str | None:
    """Try to match a brand/POI name from the resolved POIs against the user's
    raw address text. E.g. if the user typed 'Starbucks, Avenida ...' and the
    POI list includes a row with poi_primary_name='Starbucks ...', return it."""
    if not raw_input:
        return None
    input_lower = raw_input.lower()
    for col in ("brand_name_primary", "poi_primary_name"):
        if col not in brand_pois_df.columns:
            continue
        for val in brand_pois_df[col].dropna().unique():
            name = str(val).strip()
            if not name:
                continue
            name_lower = name.lower()
            first_word = name_lower.split()[0] if name_lower else ""
            if first_word and len(first_word) >= 3 and first_word in input_lower:
                log.info("Brand from input text: '%s' (matched '%s' in input)", name, first_word)
                return name
    return None


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _parse_map_selection(geojson: dict, resolution: int) -> list[dict]:
    """Extract brand locations from drawn GeoJSON features.

    Points are used directly. Polygons are H3-polyfilled and converted
    to cell centroids so they integrate with the existing pipeline.
    """
    seen_cells: set[str] = set()
    locs: list[dict] = []

    for feature in geojson.get("features", []):
        geom = feature.get("geometry", {})
        geom_type = geom.get("type")
        coords = geom.get("coordinates")
        if not coords:
            continue

        if geom_type == "Point":
            lon, lat = coords[0], coords[1]
            hex_id = h3.latlng_to_cell(lat, lon, resolution)
            if hex_id not in seen_cells:
                seen_cells.add(hex_id)
                locs.append({"lat": lat, "lon": lon})

        elif geom_type == "Polygon":
            outer_ring = coords[0]
            h3_outer = [(pt[1], pt[0]) for pt in outer_ring]
            holes = [[(pt[1], pt[0]) for pt in ring] for ring in coords[1:]]
            poly = h3.LatLngPoly(h3_outer, *holes)
            cells = h3.polygon_to_cells(poly, resolution)
            for cell in cells:
                if cell not in seen_cells:
                    seen_cells.add(cell)
                    lat, lon = h3.cell_to_latlng(cell)
                    locs.append({"lat": lat, "lon": lon})

    return locs


def _parse_locations(text: str, mode: str) -> list[dict]:
    from geopy.geocoders import Nominatim
    locs: list[dict] = []
    geocoder = Nominatim(user_agent="site-selection-accelerator") if mode == "addresses" else None
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if mode == "latlng":
            parts = line.split(",")
            if len(parts) != 2:
                continue
            try:
                lat, lon = float(parts[0].strip()), float(parts[1].strip())
                locs.append({"lat": lat, "lon": lon})
            except ValueError:
                continue
        elif geocoder is not None:
            result = geocoder.geocode(line, timeout=10)
            if result:
                locs.append({"lat": result.latitude, "lon": result.longitude, "source": line})
    return locs


def _build_hexagon_list(
    scored: pd.DataFrame,
    address_lookup: dict,
    count_vectors: pd.DataFrame,
    brand_avg: pd.Series,
) -> list[HexagonData]:
    from explainability import tooltip_snippet

    has_competition = "opportunity_score" in scored.columns
    has_radiance = "radiance" in scored.columns
    hexagons: list[HexagonData] = []
    for _, row in scored.iterrows():
        cell = int(row["h3_cell"])
        hex_id = _h3_int_to_hex(cell)
        lat, lon = _h3_center(cell)
        sim = float(row["similarity"])
        opp = float(row["opportunity_score"]) if has_competition and pd.notna(row.get("opportunity_score")) else None
        rad = round(float(row["radiance"]), 2) if has_radiance and pd.notna(row.get("radiance")) else None
        hexagons.append(HexagonData(
            h3_cell=cell,
            hex_id=hex_id,
            similarity=round(sim, 4),
            opportunity_score=round(opp, 4) if opp is not None else None,
            is_brand_cell=bool(row["is_brand_cell"]),
            lat=lat,
            lon=lon,
            address=address_lookup.get(cell, ""),
            poi_density=int(row.get("poi_density", 0)),
            radiance=rad,
            competitor_count=int(row.get("competitor_count", 0)) if has_competition else 0,
            top_competitors=str(row.get("top_competitors", "")) if has_competition else "",
            cat_detail=tooltip_snippet(cell, count_vectors, brand_avg, max_cats=4),
            cannibalization_risk=_opt_round(row.get("cannibalization_risk"), 4),
            nearest_store_km=_opt_round(row.get("nearest_store_km"), 3),
        ))
    return hexagons


def _build_brand_location_list(
    brand_locations: list[dict],
    resolution: int,
    address_lookup: dict[int, str] | None = None,
) -> list[BrandLocationData]:
    cell_counts: dict[str, int] = {}
    for loc in brand_locations:
        hex_id = h3.latlng_to_cell(loc["lat"], loc["lon"], resolution)
        cell_counts[hex_id] = cell_counts.get(hex_id, 0) + 1

    result = []
    for hex_id, count in cell_counts.items():
        lat, lon = h3.cell_to_latlng(hex_id)
        addr = ""
        if address_lookup:
            cell_int = h3.str_to_int(hex_id)
            addr = address_lookup.get(cell_int, "")
        result.append(BrandLocationData(lat=lat, lon=lon, hex_id=hex_id, count=count, address=addr))
    return result


def _build_competitor_location_list(
    competitor_pois: pd.DataFrame,
    resolution: int,
) -> list[CompetitorLocationData]:
    """Build per-cell competitor markers for the map from named competitor POIs."""
    if competitor_pois is None or competitor_pois.empty:
        return []

    if "h3_hex" not in competitor_pois.columns:
        return []

    grouped = competitor_pois.groupby("h3_hex").agg(
        count=("h3_hex", "size"),
        name=("shop_name", lambda x: x.value_counts().index[0] if len(x) > 0 else ""),
    ).reset_index()

    result: list[CompetitorLocationData] = []
    for _, row in grouped.iterrows():
        try:
            lat, lon = h3.cell_to_latlng(str(row["h3_hex"]))
            result.append(CompetitorLocationData(
                lat=lat, lon=lon,
                hex_id=str(row["h3_hex"]),
                name=str(row["name"]),
                count=int(row["count"]),
            ))
        except Exception:
            continue
    return result


def _find_named_competitor(
    competitor_brand: str,
    scored: pd.DataFrame,
    resolution: int,
    country: str,
    city: str,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Find stores of a specific named competitor via Genie.

    Returns the same (comp_per_cell, competitor_pois) tuple as
    find_competitors_in_similar_cells for downstream compatibility.
    """
    from brand_search import discover_brand_locations

    empty_agg = pd.DataFrame(columns=["h3_hex", "competitor_count", "top_competitors"])

    try:
        comp_locs, comp_cells, comp_pois_df = discover_brand_locations(
            competitor_brand, resolution, country=country, city=city,
        )
    except Exception as e:
        log.error("Named competitor Genie lookup failed for '%s': %s", competitor_brand, e)
        return empty_agg, None

    if comp_pois_df is None or comp_pois_df.empty:
        log.info("Named competitor '%s': no stores found", competitor_brand)
        return empty_agg, None

    for col in ("lon", "lat"):
        if col in comp_pois_df.columns:
            comp_pois_df[col] = pd.to_numeric(comp_pois_df[col], errors="coerce")
    comp_pois_df = comp_pois_df.dropna(subset=["lon", "lat"])
    if comp_pois_df.empty:
        log.info("Named competitor '%s': no valid coordinates", competitor_brand)
        return empty_agg, None

    comp_pois_df["h3_hex"] = comp_pois_df.apply(
        lambda r: h3.latlng_to_cell(float(r["lat"]), float(r["lon"]), resolution),
        axis=1,
    )

    scored_hexes = set(scored["h3_cell"].apply(_h3_int_to_hex))
    comp_pois_df = comp_pois_df[comp_pois_df["h3_hex"].isin(scored_hexes)].copy()
    if comp_pois_df.empty:
        log.info("Named competitor '%s': stores found but none overlap scored cells", competitor_brand)
        return empty_agg, None

    def _name(row: pd.Series) -> str:
        for col in ("brand_name_primary", "poi_primary_name"):
            val = _clean_text(row.get(col))
            if val:
                return val
        return competitor_brand

    comp_pois_df["shop_name"] = comp_pois_df.apply(_name, axis=1)

    comp_per_cell = (
        comp_pois_df.groupby("h3_hex")
        .agg(
            competitor_count=("shop_name", "size"),
            top_competitors=("shop_name", lambda names: ", ".join(
                f"{n} ({c})" for n, c in names.value_counts().head(3).items()
            )),
        )
        .reset_index()
    )

    log.info(
        "Named competitor '%s': %d stores in %d cells",
        competitor_brand, len(comp_pois_df), len(comp_per_cell),
    )
    return comp_per_cell, comp_pois_df


def _wkt_to_geojson(wkt_str: str) -> dict | None:
    try:
        from shapely import wkt
        geom = wkt.loads(wkt_str)
        return json.loads(json.dumps({
            "type": "Feature",
            "geometry": geom.__geo_interface__,
            "properties": {},
        }))
    except Exception:
        return None
