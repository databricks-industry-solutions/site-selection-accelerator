# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # Train Hex2Vec Model
# MAGIC Pre-train a Hex2Vec model on multiple cities and save to a UC Volume.
# MAGIC
# MAGIC Follows the Hex2Vec paper methodology: fit on a diverse set of cities
# MAGIC so the encoder learns general urban spatial patterns, then save the
# MAGIC model for the app to load and transform at request time.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "")
dbutils.widgets.text("warehouse_id", "")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
warehouse_id = dbutils.widgets.get("warehouse_id")

print(f"Catalog:      {catalog}")
print(f"Schema:       {schema}")
print(f"Warehouse ID: {warehouse_id}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

from __future__ import annotations

import json
import logging
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pyarrow as pa
import requests
import h3
import numpy as np
import pandas as pd
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format, StatementState
from shapely.geometry import Polygon
from srai.embedders import Hex2VecEmbedder
from srai.neighbourhoods import H3Neighbourhood

log = logging.getLogger(__name__)

ENCODER_SIZES = [48, 24, 12]
MAX_EPOCHS = 10
BATCH_SIZE = 256
H3_RESOLUTION = 9

TRAINING_CITIES: list[tuple[str, str]] = [
    ("RU", "Москва"),
    ("GB", "London"),
    ("IT", "Roma"),
    ("US", "New York"),
    ("DE", "Berlin"),
    ("FI", "Helsinki"),
    ("NO", "Oslo"),
    ("US", "Chicago"),
    ("PL", "Warszawa"),
    ("ES", "Madrid"),
    ("CZ", "Praha"),
    ("LT", "Vilnius"),
    ("KZ", "Астана"),
    ("AT", "Wien"),
    ("BY", "Мінск"),
    ("LV", "Rīga"),
    ("RS", "Београд"),
    ("SK", "Bratislava"),
    ("US", "San Francisco"),
    ("PL", "Kraków"),
    ("PL", "Gdańsk"),
    ("PL", "Wrocław"),
    ("PL", "Łódź"),
    ("HR", "Zagreb"),
    ("SE", "Stockholm"),
    ("PL", "Poznań"),
    ("IS", "Reykjavík"),
    ("SI", "Ljubljana"),
    ("NL", "Amsterdam"),
    ("EE", "Tallinn"),
    ("BG", "София"),
    ("IE", "Dublin"),
    ("FR", "Paris"),
    ("PT", "Lisboa"),
    ("LU", "Luxembourg"),
    ("CH", "Bern"),
    ("BE", "Bruxelles - Brussel"),
]

POI_CATEGORIES: list[str] = [
    "restaurant", "fast_food_restaurant", "cafe", "coffee_shop",
    "bar", "bakery", "food_truck",
    "clothing_store", "convenience_store", "grocery_store", "shopping",
    "furniture_store", "supermarket", "shopping_mall", "department_store",
    "bank", "pharmacy", "gas_station", "gym", "hospital", "dentist",
    "hair_salon", "beauty_salon", "automotive_repair",
    "movie_theater", "park", "hotel", "museum",
    "professional_services", "real_estate", "education", "school",
]

BUILDING_CATEGORIES: list[str] = [
    "bldg_residential", "bldg_commercial", "bldg_industrial",
    "bldg_agricultural", "bldg_transportation", "bldg_outbuilding",
    "bldg_other",
    "height_low_rise", "height_mid_rise", "height_high_rise",
    "height_skyscraper",
]

ALL_TRAINING_CATEGORIES: list[str] = POI_CATEGORIES + BUILDING_CATEGORIES

METADATA_FILENAME = "hex2vec_metadata.json"

# COMMAND ----------

# MAGIC %md
# MAGIC ## SQL Execution Helper

# COMMAND ----------

def _download_arrow_chunk(link) -> pa.Table:
    # Pre-signed cloud-storage URL: must NOT carry the Databricks auth header.
    resp = requests.get(link.external_link, timeout=300)
    resp.raise_for_status()
    return pa.ipc.open_stream(resp.content).read_all()


def _execute_sql(
    client: WorkspaceClient,
    warehouse_id: str,
    query: str,
    catalog: str | None = None,
    schema: str | None = None,
) -> pd.DataFrame:
    """Execute a SQL statement and return a DataFrame.

    Uses EXTERNAL_LINKS + ARROW_STREAM (same as the app's db.py). The
    previous INLINE/JSON fetch silently capped results at 25 MiB, which
    truncated the multi-city POI/building pull to ~2% of the training
    cells. A truncated result now fails the task instead.
    """
    resp = client.statement_execution.execute_statement(
        statement=query,
        warehouse_id=warehouse_id,
        catalog=catalog,
        schema=schema,
        wait_timeout="50s",
        disposition=Disposition.EXTERNAL_LINKS,
        format=Format.ARROW_STREAM,
    )

    state = resp.status.state if resp.status else None
    if state in (StatementState.PENDING, StatementState.RUNNING):
        log.info("Query still running, polling…")
        while True:
            resp = client.statement_execution.get_statement(resp.statement_id)
            if resp.status.state in (
                StatementState.SUCCEEDED, StatementState.FAILED,
                StatementState.CANCELED, StatementState.CLOSED,
            ):
                break
            time.sleep(3)

    if resp.status and resp.status.state == StatementState.FAILED:
        msg = resp.status.error.message if resp.status.error else "Unknown"
        raise RuntimeError(f"SQL failed: {msg}\nQuery: {query[:200]}")

    if resp.manifest is None or resp.result is None:
        return pd.DataFrame()

    tables = [_download_arrow_chunk(l) for l in (resp.result.external_links or [])]
    total_chunks = resp.manifest.total_chunk_count or 1
    for chunk_idx in range(1, total_chunks):
        chunk = client.statement_execution.get_statement_result_chunk_n(
            statement_id=resp.statement_id, chunk_index=chunk_idx,
        )
        tables.extend(_download_arrow_chunk(l) for l in (chunk.external_links or []))

    df = pa.concat_tables(tables).to_pandas() if tables else pd.DataFrame(
        columns=[c.name for c in resp.manifest.schema.columns]
    )
    if resp.manifest.truncated:
        raise RuntimeError(
            f"SQL result truncated: {len(df)} of {resp.manifest.total_row_count} rows"
        )
    log.info("SQL returned %d rows (%d chunks)", len(df), total_chunks)
    return df

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Collection

# COMMAND ----------

def validate_cities(
    client: WorkspaceClient,
    warehouse_id: str,
    catalog: str,
    schema: str,
    city_specs: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Check which training cities exist in gold_cities."""
    placeholders = ", ".join(
        f"('{country}', '{city}')" for country, city in city_specs
    )
    query = f"""
        SELECT DISTINCT country, city_name
        FROM {catalog}.{schema}.gold_cities
        WHERE (country, city_name) IN ({placeholders})
    """
    df = _execute_sql(client, warehouse_id, query)
    if df.empty:
        return [], list(city_specs)
    found_set = set(zip(df["country"], df["city_name"]))
    found = [cs for cs in city_specs if cs in found_set]
    missing = [cs for cs in city_specs if cs not in found_set]
    return found, missing


def _city_cells_cte(
    catalog: str, schema: str, city_specs: list[tuple[str, str]], resolution: int,
) -> str:
    """CTE `cells` = distinct H3 cells covering every training city."""
    values = ", ".join(
        "('{}', '{}')".format(c, n.replace("'", "''")) for c, n in city_specs
    )
    return f"""
        training_cities(country, city_name) AS (VALUES {values}),
        cells AS (
            SELECT DISTINCT explode(h3_polyfillash3(g.geom_wkt, {resolution})) AS h3_cell
            FROM {catalog}.{schema}.gold_cities g
            JOIN training_cities t USING (country, city_name)
        )"""


def tessellate_cities(
    client: WorkspaceClient,
    warehouse_id: str,
    catalog: str,
    schema: str,
    city_specs: list[tuple[str, str]],
    resolution: int,
) -> pd.DataFrame:
    """H3-tessellate multiple cities and return the deduplicated union."""
    query = f"""
        WITH {_city_cells_cte(catalog, schema, city_specs, resolution)}
        SELECT
            h3_cell,
            CAST(h3_centerasgeojson(h3_cell):coordinates[1] AS DOUBLE) AS center_lat,
            CAST(h3_centerasgeojson(h3_cell):coordinates[0] AS DOUBLE) AS center_lon
        FROM cells
    """
    return _execute_sql(client, warehouse_id, query)


def fetch_pois(
    client: WorkspaceClient,
    warehouse_id: str,
    catalog: str,
    schema: str,
    city_specs: list[tuple[str, str]],
    resolution: int,
    categories: list[str],
) -> pd.DataFrame:
    """Fetch POIs that fall within the training cities' H3 cells.

    The cell filter runs in the warehouse: one bounding box spanning all
    training cities (San Francisco to Astana) would pull most of the
    planet's POIs to the driver.
    """
    cat_list = ", ".join(f"'{c}'" for c in categories)
    query = f"""
        WITH {_city_cells_cte(catalog, schema, city_specs, resolution)}
        SELECT p.poi_id, p.category, p.lon, p.lat, c.h3_cell
        FROM {catalog}.{schema}.gold_places p
        JOIN cells c ON h3_longlatash3(p.lon, p.lat, {resolution}) = c.h3_cell
        WHERE p.category IN ({cat_list})
    """
    return _execute_sql(client, warehouse_id, query)


def fetch_buildings(
    client: WorkspaceClient,
    warehouse_id: str,
    catalog: str,
    schema: str,
    city_specs: list[tuple[str, str]],
    resolution: int,
) -> pd.DataFrame:
    """Fetch buildings that fall within the training cities' H3 cells."""
    query = f"""
        WITH {_city_cells_cte(catalog, schema, city_specs, resolution)}
        SELECT b.building_id, b.building_category, b.height_bin, b.lon, b.lat, b.h3_cell
        FROM {catalog}.{schema}.gold_buildings b
        JOIN cells c ON b.h3_cell = c.h3_cell
    """
    return _execute_sql(client, warehouse_id, query)

# COMMAND ----------

# MAGIC %md
# MAGIC ## SRAI GeoDataFrame Builders

# COMMAND ----------

def _int_to_hex(cell_id: int) -> str:
    return h3.int_to_str(int(cell_id))


def _h3_hex_to_polygon(hex_id: str) -> Polygon:
    boundary = h3.cell_to_boundary(hex_id)
    return Polygon([(lon, lat) for lat, lon in boundary])


def _normalise_buildings(buildings_df: pd.DataFrame) -> pd.DataFrame:
    """Expand buildings into feature rows (category + height_bin)."""
    if buildings_df.empty:
        return pd.DataFrame(
            columns=["feature_id", "category", "lon", "lat", "h3_cell"]
        )
    cat_rows = buildings_df[
        ["building_id", "building_category", "lon", "lat", "h3_cell"]
    ].copy()
    cat_rows = cat_rows.rename(
        columns={"building_id": "feature_id", "building_category": "category"}
    )
    cat_rows["feature_id"] = "bc_" + cat_rows["feature_id"].astype(str)

    height_rows = buildings_df[buildings_df["height_bin"].notna()].copy()
    if not height_rows.empty:
        height_rows = height_rows[
            ["building_id", "height_bin", "lon", "lat", "h3_cell"]
        ]
        height_rows = height_rows.rename(
            columns={"building_id": "feature_id", "height_bin": "category"}
        )
        height_rows["feature_id"] = "bh_" + height_rows["feature_id"].astype(str)
        return pd.concat([cat_rows, height_rows], ignore_index=True)

    return cat_rows.reset_index(drop=True)


def build_regions_gdf(h3_cells_df: pd.DataFrame) -> gpd.GeoDataFrame:
    unique_ints = h3_cells_df["h3_cell"].unique()
    hex_ids = [_int_to_hex(c) for c in unique_ints]
    polys = [_h3_hex_to_polygon(h) for h in hex_ids]
    return gpd.GeoDataFrame(
        {"geometry": polys},
        index=pd.Index(hex_ids, name="region_id"),
        crs="EPSG:4326",
    )


def build_features_gdf(
    features_df: pd.DataFrame,
    categories: list[str],
) -> gpd.GeoDataFrame:
    geom = gpd.points_from_xy(features_df["lon"], features_df["lat"])
    gdf = gpd.GeoDataFrame(features_df, geometry=geom, crs="EPSG:4326")
    gdf = gdf.set_index("feature_id")
    gdf.index.name = "feature_id"

    dummies = pd.get_dummies(gdf["category"], dtype="int8")
    for cat in categories:
        if cat not in dummies.columns:
            dummies[cat] = np.zeros(len(dummies), dtype="int8")
    gdf = pd.concat([gdf, dummies[categories]], axis=1)
    gdf = gdf.drop(
        columns=["category", "lon", "lat", "address", "h3_cell"],
        errors="ignore",
    )
    return gdf


def build_joint_gdf(features_df: pd.DataFrame) -> pd.DataFrame:
    joint = features_df[["h3_cell", "feature_id"]].copy()
    joint["h3_cell"] = joint["h3_cell"].apply(_int_to_hex)
    joint = joint.rename(columns={"h3_cell": "region_id"})
    return joint.set_index(["region_id", "feature_id"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Training Pipeline

# COMMAND ----------

def main(catalog: str, schema: str, warehouse_id: str) -> str:
    """Train Hex2Vec on multiple cities and save to a UC Volume."""
    client = WorkspaceClient()

    volume_path = f"/Volumes/{catalog}/{schema}/models"
    model_path = f"{volume_path}/hex2vec"

    _execute_sql(
        client, warehouse_id,
        f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.models",
    )

    log.info("Validating %d training cities…", len(TRAINING_CITIES))
    found, missing = validate_cities(
        client, warehouse_id, catalog, schema, TRAINING_CITIES,
    )
    if missing:
        log.warning(
            "Missing %d cities from gold_cities: %s",
            len(missing),
            ", ".join(f"{c}/{n}" for c, n in missing),
        )
    if not found:
        raise RuntimeError("No training cities found in gold_cities.")
    log.info("Training on %d cities", len(found))

    log.info("Tessellating %d cities at resolution %d…", len(found), H3_RESOLUTION)
    h3_cells_df = tessellate_cities(
        client, warehouse_id, catalog, schema, found, H3_RESOLUTION,
    )
    log.info("Total H3 cells: %d", len(h3_cells_df))

    log.info("Fetching POIs for %d categories…", len(POI_CATEGORIES))
    pois_df = fetch_pois(
        client, warehouse_id, catalog, schema,
        found, H3_RESOLUTION, POI_CATEGORIES,
    )
    log.info("POIs fetched: %d", len(pois_df))

    poi_features = pois_df[["poi_id", "category", "lon", "lat", "h3_cell"]].copy()
    poi_features = poi_features.rename(columns={"poi_id": "feature_id"})

    log.info("Fetching buildings…")
    bldg_df = fetch_buildings(
        client, warehouse_id, catalog, schema, found, H3_RESOLUTION,
    )
    log.info("Buildings fetched: %d", len(bldg_df))

    bldg_features = _normalise_buildings(bldg_df)

    if not bldg_features.empty:
        features_df = pd.concat(
            [poi_features, bldg_features], ignore_index=True,
        )
    else:
        features_df = poi_features

    log.info("Total features: %d", len(features_df))

    log.info("Building GeoDataFrames…")
    regions_gdf = build_regions_gdf(h3_cells_df)
    features_gdf = build_features_gdf(features_df, ALL_TRAINING_CATEGORIES)
    joint_gdf = build_joint_gdf(features_df)

    valid_regions = joint_gdf.index.get_level_values("region_id").unique()
    regions_gdf = regions_gdf.loc[regions_gdf.index.isin(valid_regions)]

    valid_features = joint_gdf.index.get_level_values("feature_id").unique()
    features_gdf = features_gdf.loc[features_gdf.index.isin(valid_features)]

    log.info(
        "Regions with features: %d / %d, Features: %d",
        len(regions_gdf), len(h3_cells_df), len(features_gdf),
    )

    if regions_gdf.empty or features_gdf.empty:
        raise RuntimeError("No feature data intersects any H3 cells.")

    neighbourhood = H3Neighbourhood(regions_gdf)
    log.info(
        "Fitting Hex2Vec: encoder=%s, epochs=%d, batch_size=%d",
        ENCODER_SIZES, MAX_EPOCHS, BATCH_SIZE,
    )

    embedder = Hex2VecEmbedder(encoder_sizes=ENCODER_SIZES)
    embedder.fit(
        regions_gdf, features_gdf, joint_gdf, neighbourhood,
        trainer_kwargs={"max_epochs": MAX_EPOCHS, "accelerator": "cpu"},
        batch_size=BATCH_SIZE,
    )
    log.info("Hex2Vec fitting complete.")

    with tempfile.TemporaryDirectory() as tmp:
        local_dir = Path(tmp) / "hex2vec"
        local_dir.mkdir()

        embedder.save(local_dir)

        metadata = {
            "categories": ALL_TRAINING_CATEGORIES,
            "resolution": H3_RESOLUTION,
            "encoder_sizes": ENCODER_SIZES,
            "max_epochs": MAX_EPOCHS,
            "batch_size": BATCH_SIZE,
            "cities": [list(c) for c in found],
            "num_regions": len(regions_gdf),
            "num_city_cells": len(h3_cells_df),
            "num_features": len(features_gdf),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        (local_dir / METADATA_FILENAME).write_text(
            json.dumps(metadata, indent=2)
        )

        for src_file in local_dir.iterdir():
            if not src_file.is_file():
                continue
            dest_path = f"{model_path}/{src_file.name}"
            log.info("Uploading %s -> %s", src_file.name, dest_path)
            with open(src_file, "rb") as f:
                client.files.upload(dest_path, f, overwrite=True)

    log.info("Model saved to %s", model_path)
    return model_path

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute

# COMMAND ----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

result = main(catalog, schema, warehouse_id)
print(f"HEX2VEC_MODEL_PATH={result}")
