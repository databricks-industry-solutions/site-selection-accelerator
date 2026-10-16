"""Persist analysis results to Delta tables via DBSQL Statement Execution API.

Uses the same db.execute_query helper as the rest of the app to write
analysis artifacts into the catalog/schema configured in config.py.

Bulk writes serialize DataFrames to Parquet, upload to a temporary UC
Volume, then COPY INTO the target Delta table for atomicity and speed.
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import h3
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import (
    ANALYSES_TABLE,
    ANALYSIS_BRAND_PROFILES_TABLE,
    ANALYSIS_COMPETITORS_TABLE,
    ANALYSIS_FINGERPRINTS_TABLE,
    ANALYSIS_HEXAGONS_TABLE,
    ALL_BUILDING_CATEGORIES,
    ALL_FEATURE_GROUPS,
    TMP_VOLUME_PATH,
)
from db import execute_query, _get_client

if TYPE_CHECKING:
    from cache import PipelineResult

log = logging.getLogger(__name__)

_tables_ensured = False


def _sql_str(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def _sql_val(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return _sql_str(str(value))


def _copy_into(df: pd.DataFrame, table: str, analysis_id: str, suffix: str) -> None:
    """Upload *df* as Parquet to a temp volume and COPY INTO *table*."""
    if df.empty:
        return

    buf = io.BytesIO()
    arrow_table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(arrow_table, buf)
    buf.seek(0)

    vol_path = f"{TMP_VOLUME_PATH}/{analysis_id}/{suffix}.parquet"
    client = _get_client()
    client.files.upload(vol_path, buf, overwrite=True)

    try:
        execute_query(
            f"COPY INTO {table} "
            f"FROM '{vol_path}' "
            f"FILEFORMAT = PARQUET "
            f"FORMAT_OPTIONS ('mergeSchema' = 'true')"
        )
    finally:
        try:
            client.files.delete(vol_path)
        except Exception as exc:
            log.warning("Failed to delete temp file %s: %s", vol_path, exc)


def ensure_analysis_tables() -> None:
    """Create analysis tables if they don't already exist."""
    global _tables_ensured
    if _tables_ensured:
        return

    ddl_statements = [
        f"""CREATE TABLE IF NOT EXISTS {ANALYSES_TABLE} (
            analysis_id STRING NOT NULL, session_id STRING NOT NULL,
            brand_input_mode STRING, brand_input_value STRING,
            country STRING, city STRING, h3_resolution INT,
            categories STRING, enable_competition BOOLEAN,
            beta DOUBLE, include_buildings BOOLEAN,
            city_polygon_geojson STRING,
            center_lat DOUBLE, center_lon DOUBLE,
            created_at TIMESTAMP, created_by STRING
        ) USING DELTA CLUSTER BY (analysis_id)""",
        f"""CREATE TABLE IF NOT EXISTS {ANALYSIS_BRAND_PROFILES_TABLE} (
            analysis_id STRING NOT NULL, category STRING,
            avg_count DOUBLE, pct_within_type DOUBLE,
            feature_type STRING, group_name STRING
        ) USING DELTA CLUSTER BY (analysis_id)""",
        f"""CREATE TABLE IF NOT EXISTS {ANALYSIS_HEXAGONS_TABLE} (
            analysis_id STRING NOT NULL, h3_cell BIGINT, hex_id STRING,
            similarity DOUBLE, opportunity_score DOUBLE,
            is_brand_cell BOOLEAN, lat DOUBLE, lon DOUBLE,
            address STRING, poi_count INT, competitor_count INT,
            top_competitors STRING,
            cannibalization_risk DOUBLE, nearest_store_km DOUBLE
        ) USING DELTA CLUSTER BY (analysis_id, similarity)""",
        f"""CREATE TABLE IF NOT EXISTS {ANALYSIS_FINGERPRINTS_TABLE} (
            analysis_id STRING NOT NULL, hex_id STRING,
            category STRING, group_name STRING, feature_type STRING,
            this_location DOUBLE, brand_average DOUBLE,
            this_location_pct DOUBLE, brand_average_pct DOUBLE,
            explanation_summary STRING
        ) USING DELTA CLUSTER BY (analysis_id)""",
        f"""CREATE TABLE IF NOT EXISTS {ANALYSIS_COMPETITORS_TABLE} (
            analysis_id STRING NOT NULL, hex_id STRING,
            poi_name STRING, category STRING,
            brand STRING, address STRING
        ) USING DELTA CLUSTER BY (analysis_id)""",
    ]

    for ddl in ddl_statements:
        try:
            execute_query(ddl)
        except Exception as e:
            log.error("DDL execution failed — tables may be missing: %s", e)
            raise RuntimeError(
                f"Failed to create analysis tables: {e}. "
                "Check that the catalog/schema exist and the app service principal "
                "has CREATE TABLE permission."
            ) from e

    _tables_ensured = True
    log.info("Analysis tables ensured")


def _h3_int_to_hex(cell_id: int) -> str:
    if cell_id < 0:
        cell_id = cell_id + (1 << 64)
    return h3.int_to_str(cell_id)


def persist_analysis(
    session_id: str,
    request_data: dict,
    pipeline_result: PipelineResult,
    city_polygon_geojson: dict | None,
    center_lat: float,
    center_lon: float,
    user_identity: str = "",
    top_n_fingerprints: int = 20,
    analysis_id: str | None = None,
) -> dict:
    """Persist all analysis artifacts to Delta and return metadata.

    Parameters
    ----------
    session_id : str
        In-memory cache session id.
    request_data : dict
        The original AnalyzeRequest fields.
    pipeline_result : PipelineResult
        The cached pipeline result.
    city_polygon_geojson : dict | None
        City polygon GeoJSON for the analyses table.
    center_lat, center_lon : float
        Map center coordinates.
    user_identity : str
        User who triggered the analysis.
    top_n_fingerprints : int
        How many top hexagons to compute fingerprints for.
    analysis_id : str | None
        Supply a deterministic id for idempotent retries. A fresh UUID
        is generated when ``None``.

    Returns
    -------
    dict with analysis_id and list of tables written.
    """
    ensure_analysis_tables()

    if analysis_id is None:
        analysis_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    tables_written: list[str] = []

    _persist_analyses_row(analysis_id, session_id, request_data,
                          city_polygon_geojson, center_lat, center_lon,
                          now, user_identity)
    tables_written.append(ANALYSES_TABLE)

    try:
        _persist_brand_profile(analysis_id, pipeline_result)
        tables_written.append(ANALYSIS_BRAND_PROFILES_TABLE)
    except Exception as e:
        log.error("Failed to persist brand profiles: %s", e)

    try:
        _persist_hexagons(analysis_id, pipeline_result)
        tables_written.append(ANALYSIS_HEXAGONS_TABLE)
    except Exception as e:
        log.error("Failed to persist hexagons: %s", e)

    try:
        _persist_competitors(analysis_id, pipeline_result)
        tables_written.append(ANALYSIS_COMPETITORS_TABLE)
    except Exception as e:
        log.error("Failed to persist competitors: %s", e)

    try:
        _persist_fingerprints(analysis_id, pipeline_result, top_n_fingerprints)
        tables_written.append(ANALYSIS_FINGERPRINTS_TABLE)
    except Exception as e:
        log.error("Failed to persist fingerprints: %s", e)

    log.info("Persisted analysis %s for session %s", analysis_id, session_id)
    return {
        "analysis_id": analysis_id,
        "tables_written": tables_written,
    }


def _persist_analyses_row(
    analysis_id: str, session_id: str, req: dict,
    city_polygon_geojson: dict | None,
    center_lat: float, center_lon: float,
    created_at: str, created_by: str,
) -> None:
    poly_json = json.dumps(city_polygon_geojson) if city_polygon_geojson else None
    cats_json = json.dumps(req.get("categories", []))

    sql = f"""INSERT INTO {ANALYSES_TABLE} VALUES (
        {_sql_str(analysis_id)}, {_sql_str(session_id)},
        {_sql_str(req.get('brand_input_mode'))},
        {_sql_str(req.get('brand_input_value'))},
        {_sql_str(req.get('country'))}, {_sql_str(req.get('city'))},
        {_sql_val(req.get('resolution', 9))},
        {_sql_str(cats_json)},
        {_sql_val(req.get('enable_competition', True))},
        {_sql_val(req.get('beta', 1.0))},
        {_sql_val(req.get('include_buildings', True))},
        {_sql_str(poly_json)},
        {_sql_val(center_lat)}, {_sql_val(center_lon)},
        TIMESTAMP '{created_at}',
        {_sql_str(created_by)}
    )"""
    execute_query(sql)


def _persist_brand_profile(analysis_id: str, pr: PipelineResult) -> None:
    brand_avg = pr.brand_avg
    avg_nonzero = brand_avg[brand_avg > 0]
    if avg_nonzero.empty:
        return

    bldg_set = set(ALL_BUILDING_CATEGORIES)
    group_lookup = {}
    for grp, cats in ALL_FEATURE_GROUPS.items():
        for c in cats:
            group_lookup[c] = grp

    poi_total = sum(v for c, v in avg_nonzero.items() if c not in bldg_set)
    bldg_total = sum(v for c, v in avg_nonzero.items() if c in bldg_set)

    records = []
    for cat, avg_count in avg_nonzero.items():
        ft = "Building" if cat in bldg_set else "POI"
        ft_total = bldg_total if cat in bldg_set else poi_total
        pct = round(avg_count / ft_total * 100, 1) if ft_total > 0 else 0.0
        grp = group_lookup.get(cat, "Other")
        records.append({
            "analysis_id": analysis_id,
            "category": cat,
            "avg_count": round(float(avg_count), 2),
            "pct_within_type": pct,
            "feature_type": ft,
            "group_name": grp,
        })

    _copy_into(pd.DataFrame(records), ANALYSIS_BRAND_PROFILES_TABLE, analysis_id, "brand_profiles")


def _persist_hexagons(analysis_id: str, pr: PipelineResult) -> None:
    scored = pr.scored.copy()
    has_competition = "opportunity_score" in scored.columns

    scored["analysis_id"] = analysis_id
    scored["hex_id"] = scored["h3_cell"].apply(lambda c: _h3_int_to_hex(int(c)))

    latlng = scored["hex_id"].apply(lambda h: h3.cell_to_latlng(h))
    scored["lat"] = latlng.apply(lambda ll: ll[0])
    scored["lon"] = latlng.apply(lambda ll: ll[1])

    scored["similarity"] = scored["similarity"].round(4)
    scored["is_brand_cell"] = scored["is_brand_cell"].astype(bool)
    scored["address"] = scored["h3_cell"].map(pr.address_lookup).fillna("")
    scored["poi_count"] = scored.get("poi_density", pd.Series(0, index=scored.index)).fillna(0).astype(int)

    if has_competition:
        scored["opportunity_score"] = scored["opportunity_score"].round(4)
        scored["competitor_count"] = scored.get("competitor_count", pd.Series(0, index=scored.index)).fillna(0).astype(int)
        scored["top_competitors"] = scored.get("top_competitors", pd.Series("", index=scored.index)).fillna("").astype(str)
    else:
        scored["opportunity_score"] = np.nan
        scored["competitor_count"] = 0
        scored["top_competitors"] = ""

    for col in ("cannibalization_risk", "nearest_store_km"):
        if col not in scored.columns:
            scored[col] = np.nan

    out = scored[
        ["analysis_id", "h3_cell", "hex_id", "similarity", "opportunity_score",
         "is_brand_cell", "lat", "lon", "address", "poi_count",
         "competitor_count", "top_competitors",
         "cannibalization_risk", "nearest_store_km"]
    ].copy()

    _copy_into(out, ANALYSIS_HEXAGONS_TABLE, analysis_id, "hexagons")


def _persist_competitors(analysis_id: str, pr: PipelineResult) -> None:
    if pr.competitor_pois is None or pr.competitor_pois.empty:
        return

    cp = pr.competitor_pois
    out = pd.DataFrame({
        "analysis_id": analysis_id,
        "hex_id": cp.get("h3_hex", pd.Series("", index=cp.index)).fillna("").astype(str),
        "poi_name": cp.get("poi_primary_name", pd.Series("", index=cp.index)).fillna("").astype(str),
        "category": cp.get("basic_category", cp.get("poi_primary_category", pd.Series("", index=cp.index))).fillna("").astype(str),
        "brand": cp.get("brand_name_primary", pd.Series("", index=cp.index)).fillna("").astype(str),
        "address": cp.get("address_line", pd.Series("", index=cp.index)).fillna("").astype(str),
    })

    _copy_into(out, ANALYSIS_COMPETITORS_TABLE, analysis_id, "competitors")


def _persist_fingerprints(analysis_id: str, pr: PipelineResult, top_n: int) -> None:
    """Compute and persist fingerprints for the top N hexagons by similarity."""
    from explainability import build_fingerprint_df, summarise_fingerprint

    scored = pr.scored
    top_cells = scored.nlargest(top_n, "similarity")

    records: list[dict] = []
    for _, hex_row in top_cells.iterrows():
        cell = int(hex_row["h3_cell"])
        hex_id = _h3_int_to_hex(cell)

        fp_df = build_fingerprint_df(cell, pr.count_vectors, pr.brand_avg)
        if fp_df.empty:
            continue

        try:
            summary = summarise_fingerprint(fp_df)
        except Exception as e:
            log.warning("Fingerprint LLM failed for %s: %s", hex_id, e)
            summary = ""

        non_zero = fp_df[
            (fp_df["This Location"] > 0) | (fp_df["Brand Average"] > 0)
        ]
        for _, fp_row in non_zero.iterrows():
            records.append({
                "analysis_id": analysis_id,
                "hex_id": hex_id,
                "category": fp_row["category_raw"],
                "group_name": fp_row["Group"],
                "feature_type": fp_row["Feature Type"],
                "this_location": float(fp_row["This Location"]),
                "brand_average": float(fp_row["Brand Average"]),
                "this_location_pct": float(fp_row["This Location (%)"]),
                "brand_average_pct": float(fp_row["Brand Average (%)"]),
                "explanation_summary": summary,
            })

    _copy_into(pd.DataFrame(records), ANALYSIS_FINGERPRINTS_TABLE, analysis_id, "fingerprints")


def list_analyses(limit: int = 20) -> list[dict]:
    """Return recent analyses from the registry table."""
    from databricks.sdk.service.sql import StatementParameterListItem

    try:
        df = execute_query(
            f"SELECT analysis_id, brand_input_value, city, country, created_at "
            f"FROM {ANALYSES_TABLE} "
            f"ORDER BY created_at DESC LIMIT :lim",
            params=[StatementParameterListItem(name="lim", value=str(limit), type="INT")],
        )
        if df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as e:
        log.warning("Could not list analyses: %s", e)
        return []
