# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # Setup Genie Space
# MAGIC Provision (or update) the Genie Space for the Site Selection app.
# MAGIC
# MAGIC If a Genie Space with the expected name already exists, its ID is
# MAGIC reused and its full configuration (tables, instructions, sample questions)
# MAGIC is updated; otherwise a new one is created.
# MAGIC
# MAGIC The space_id is written to a small key-value table so the app can
# MAGIC read it at startup without hard-coding IDs.

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
# MAGIC ## Imports & Constants

# COMMAND ----------

import json
import logging
import uuid

from databricks.sdk import WorkspaceClient

log = logging.getLogger(__name__)

GENIE_DISPLAY_NAME = "Site Selection - Brand & Competition Explorer"

GENIE_DESCRIPTION = (
    "Explore POI data for brand site selection and competitive analysis. "
    "Uses H3 polygon fill (h3_polyfillash3) with city boundaries from "
    "gold_cities for fast spatial filtering."
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build Serialized Space

# COMMAND ----------

def _build_serialized_space(catalog: str, schema: str, existing_tables: set[str] | None = None) -> str:
    """Build the full serialized_space JSON with tables, instructions,
    and sample question-SQL pairs."""
    enriched_table = f"{catalog}.{schema}.gold_places_enriched"
    cities_table = f"{catalog}.{schema}.gold_cities"
    buildings_table = f"{catalog}.{schema}.gold_buildings"
    radiance_table = f"{catalog}.{schema}.gold_radiance"

    candidate_tables = [cities_table, enriched_table, buildings_table, radiance_table]
    if existing_tables is not None:
        candidate_tables = [t for t in candidate_tables if t in existing_tables]
    tables = [{"identifier": t} for t in candidate_tables]

    analysis_table_names = [
        "analyses",
        "analysis_brand_profiles",
        "analysis_hexagons",
        "analysis_fingerprints",
        "analysis_competitors",
    ]
    for t in analysis_table_names:
        fqn = f"{catalog}.{schema}.{t}"
        if existing_tables is None or fqn in existing_tables:
            tables.append({"identifier": fqn})

    return json.dumps({
        "version": 2,
        "data_sources": {
            "tables": sorted(tables, key=lambda t: t["identifier"]),
        },
        "config": {
            "sample_questions": [
                {
                    "id": uuid.uuid4().hex[:32],
                    "question": [
                        "Find all Starbucks locations within the city "
                        "boundary of London, GB"
                    ],
                },
                {
                    "id": uuid.uuid4().hex[:32],
                    "question": [
                        "Count businesses by basic_category within the "
                        "London, GB city polygon"
                    ],
                },
                {
                    "id": uuid.uuid4().hex[:32],
                    "question": [
                        "List distinct brand_name_primary for hotels "
                        "within the Manchester, GB city polygon"
                    ],
                },
                {
                    "id": uuid.uuid4().hex[:32],
                    "question": [
                        "Show the top 10 highest-similarity hexagons "
                        "from the most recent analysis"
                    ],
                },
                {
                    "id": uuid.uuid4().hex[:32],
                    "question": [
                        "How many analyses have been run, and for which "
                        "brands and cities?"
                    ],
                },
            ],
        },
        "instructions": {
            "text_instructions": [
                {
                    "id": uuid.uuid4().hex[:32],
                    "content": [
                        "CITY/LOCATION FILTERING — use H3 polygon fill "
                        "for fast spatial queries:\n",
                        "\n",
                        "Step 1: Build the set of H3 cells covering the "
                        "city polygon (CTE). Filter gold_cities by both "
                        "country AND city_name to pick the right polygon.\n",
                        "Step 2: JOIN gold_places_enriched to gold_cities "
                        "on TRIM(p.country) = TRIM(c.country) AND "
                        "c.city_name = '{city}'.\n",
                        "Step 3: The H3 cell membership check MUST come "
                        "first as the primary WHERE predicate — this is "
                        "the fast filter.\n",
                        "\n",
                        "Pattern (replace {city}, {country}, {resolution}):\n",
                        "  WITH city_h3 AS (\n",
                        "      SELECT explode(h3_polyfillash3(\n",
                        "          c.geom_wkt, {resolution}\n",
                        "      )) AS h3_cell\n",
                        f"      FROM {cities_table} c\n",
                        "      WHERE c.country = '{country}'\n",
                        "        AND c.city_name = '{city}'\n",
                        "  )\n",
                        f"  SELECT p.*, h3_h3tostring(\n",
                        "      h3_longlatash3(p.lon, p.lat, {resolution})\n",
                        "  ) AS h3_cell\n",
                        f"  FROM {enriched_table} p\n",
                        "  WHERE h3_longlatash3(p.lon, p.lat, {resolution})\n",
                        "        IN (SELECT h3_cell FROM city_h3)\n",
                        "    AND p.lon IS NOT NULL AND p.lat IS NOT NULL\n",
                        "\n",
                        "NEVER use ST_CONTAINS to filter individual POIs "
                        "row-by-row — it is too slow.\n",
                        "NEVER filter by the locality text column — it is "
                        "unreliable (e.g. London POIs may have locality = "
                        "'Westminster', 'Camden', etc.)\n",
                        "\n",
                        "H3 OUTPUT: always return h3 as hex string via "
                        "h3_h3tostring(h3_longlatash3(lon, lat, "
                        "{resolution})) AS h3_cell\n",
                        "\n",
                        "BRAND MATCHING: match on brand_name_primary "
                        "(ILIKE) first, fall back to poi_primary_name "
                        "ILIKE. Use OR:\n",
                        "  (p.brand_name_primary ILIKE '%Brand%' "
                        "OR p.poi_primary_name ILIKE '%Brand%')\n",
                        "\n",
                        "ANALYSIS RESULTS — The app persists analysis "
                        "outcomes to Delta tables. Each analysis run has a "
                        "unique analysis_id.\n",
                        "\n",
                        "Key tables:\n",
                        f"  {catalog}.{schema}.analyses — registry of all "
                        "runs (brand, city, parameters, timestamps)\n",
                        f"  {catalog}.{schema}.analysis_hexagons — scored "
                        "H3 hexagons with similarity and opportunity scores\n",
                        f"  {catalog}.{schema}.analysis_brand_profiles — "
                        "average POI/building category breakdown per analysis\n",
                        f"  {catalog}.{schema}.analysis_fingerprints — "
                        "per-hexagon category comparison with LLM insights\n",
                        f"  {catalog}.{schema}.analysis_competitors — "
                        "competitor POIs found in high-similarity cells\n",
                        "\n",
                        "To query a specific analysis, always filter by "
                        "analysis_id. Join analysis_hexagons to analyses "
                        "on analysis_id to get the brand/city context.\n",
                        "Example: SELECT h.hex_id, h.similarity FROM "
                        f"{catalog}.{schema}.analysis_hexagons h JOIN "
                        f"{catalog}.{schema}.analyses a ON "
                        "a.analysis_id = h.analysis_id WHERE "
                        "a.brand_input_value ILIKE '%Starbucks%' "
                        "AND NOT h.is_brand_cell "
                        "ORDER BY h.similarity DESC LIMIT 10\n",
                        "\n",
                        "CANDIDATE SITES vs EXISTING STORES — rows with "
                        "is_brand_cell = true are the brand's EXISTING "
                        "locations, not opportunities. Whenever the user "
                        "asks for opportunities, candidate sites, whitespace "
                        "or 'top hexagons', filter NOT is_brand_cell.\n",
                        "CANNIBALIZATION — analysis_hexagons."
                        "cannibalization_risk (0–1) is the share of a "
                        "candidate's walk-in catchment (default 0.8 km) "
                        "already covered by the brand's nearest existing "
                        "store; nearest_store_km is the distance to it. "
                        "Treat cannibalization_risk >= 0.5 as high. When "
                        "ranking opportunities, show cannibalization_risk "
                        "and nearest_store_km alongside opportunity_score "
                        "rather than silently filtering on them.\n",
                        "\n",
                        "RADIANCE DATA:\n",
                        f"  {catalog}.{schema}.gold_radiance — VIIRS "
                        "nighttime radiance per H3 cell. Join on h3_cell "
                        "to get economic activity context.\n",
                        "\n",
                        "BUILDINGS DATA:\n",
                        f"  {catalog}.{schema}.gold_buildings — building "
                        "footprints with type (residential, commercial, etc.) "
                        "and height bins. Pre-computed h3_cell at resolution 9.\n",
                    ],
                },
            ],
            "example_question_sqls": [
                {
                    "id": uuid.uuid4().hex[:32],
                    "question": [
                        "Find all Starbucks locations within the city "
                        "boundary of London, GB. Return poi_id, "
                        "poi_primary_name, basic_category, "
                        "brand_name_primary, lon, lat, h3_cell"
                    ],
                    "sql": [
                        "WITH city_h3 AS (\n",
                        "    SELECT explode(h3_polyfillash3(\n",
                        "        geom_wkt, 9\n",
                        "    )) AS h3_cell\n",
                        f"    FROM {cities_table}\n",
                        "    WHERE country = 'GB'\n",
                        "      AND city_name = 'London'\n",
                        ")\n",
                        "SELECT p.poi_id, p.poi_primary_name, "
                        "p.basic_category, p.brand_name_primary, "
                        "p.lon, p.lat,\n",
                        "       h3_h3tostring(h3_longlatash3(p.lon, "
                        "p.lat, 9)) AS h3_cell\n",
                        f"FROM {enriched_table} p\n",
                        "WHERE h3_longlatash3(p.lon, p.lat, 9) "
                        "IN (SELECT h3_cell FROM city_h3)\n",
                        "  AND (p.brand_name_primary ILIKE '%Starbucks%' "
                        "OR p.poi_primary_name ILIKE '%Starbucks%')\n",
                        "  AND p.lon IS NOT NULL AND p.lat IS NOT NULL\n",
                    ],
                },
            ],
        },
    })

# COMMAND ----------

# MAGIC %md
# MAGIC ## REST API Helpers

# COMMAND ----------

def _api(w: WorkspaceClient, method: str, path: str, body: dict | None = None):
    """Thin wrapper around the SDK's API client for REST calls."""
    resp = w.api_client.do(method, path, body=body)
    if isinstance(resp, bytes):
        return json.loads(resp)
    return resp


def _find_existing_space(w: WorkspaceClient) -> str | None:
    """Return the space_id of an existing Genie Space matching our name."""
    try:
        resp = _api(w, "GET", "/api/2.0/genie/spaces")
        for space in resp.get("spaces", []):
            if space.get("title") == GENIE_DISPLAY_NAME:
                sid = space.get("space_id") or space.get("id")
                log.info("Found existing Genie Space: %s", sid)
                return sid
    except Exception as e:
        log.warning("Could not list Genie Spaces: %s", e)
    return None

# COMMAND ----------

# MAGIC %md
# MAGIC ## Space CRUD

# COMMAND ----------

def _discover_existing_tables(w: WorkspaceClient, warehouse_id: str, catalog: str, schema: str) -> set[str]:
    """Return the set of fully-qualified table names that exist in the schema."""
    from databricks.sdk.service.sql import StatementState
    try:
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=f"SHOW TABLES IN `{catalog}`.`{schema}`",
            wait_timeout="30s",
        )
        if resp.status and resp.status.state == StatementState.SUCCEEDED and resp.result:
            tables = set()
            for row in (resp.result.data_array or []):
                if row and len(row) >= 2:
                    tables.add(f"{catalog}.{schema}.{row[1]}")
            log.info("Discovered %d tables in %s.%s", len(tables), catalog, schema)
            return tables
    except Exception as e:
        log.warning("Could not discover tables: %s", e)
    return set()


def _create_space(
    w: WorkspaceClient,
    catalog: str,
    schema: str,
    warehouse_id: str,
    existing_tables: set[str] | None = None,
) -> str:
    """Create a new Genie Space via REST API and return its ID."""
    serialized = _build_serialized_space(catalog, schema, existing_tables)

    resp = _api(w, "POST", "/api/2.0/genie/spaces", {
        "warehouse_id": warehouse_id,
        "serialized_space": serialized,
        "title": GENIE_DISPLAY_NAME,
        "description": GENIE_DESCRIPTION,
    })
    space_id = resp.get("space_id") or resp.get("id")
    log.info("Created Genie Space: %s", space_id)
    return space_id


def _update_space(
    w: WorkspaceClient,
    space_id: str,
    catalog: str,
    schema: str,
    existing_tables: set[str] | None = None,
) -> None:
    """Update an existing Genie Space with the latest tables, instructions, and sample questions."""
    serialized = _build_serialized_space(catalog, schema, existing_tables)
    try:
        _api(w, "PATCH", f"/api/2.0/genie/spaces/{space_id}", {
            "title": GENIE_DISPLAY_NAME,
            "description": GENIE_DESCRIPTION,
            "serialized_space": serialized,
        })
        log.info("Updated Genie Space: %s", space_id)
    except Exception as e:
        log.warning("Could not update space: %s", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Permissions & Persistence

# COMMAND ----------

def _persist_space_id(
    w: WorkspaceClient,
    catalog: str,
    schema: str,
    space_id: str,
    warehouse_id: str,
) -> None:
    """Write the space_id into a small config table so the app can read it."""
    from databricks.sdk.service.sql import StatementState

    table = f"{catalog}.{schema}.app_config"
    statements = [
        f"""CREATE TABLE IF NOT EXISTS {table} (
            config_key STRING NOT NULL,
            config_value STRING NOT NULL
        ) USING DELTA""",
        f"""MERGE INTO {table} t
        USING (SELECT 'GENIE_SPACE_ID' AS config_key,
                      '{space_id}' AS config_value) s
        ON t.config_key = s.config_key
        WHEN MATCHED THEN UPDATE SET config_value = s.config_value
        WHEN NOT MATCHED THEN INSERT (config_key, config_value)
            VALUES (s.config_key, s.config_value)""",
    ]
    for stmt in statements:
        resp = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            catalog=catalog,
            schema=schema,
            statement=stmt,
        )
        if resp.status and resp.status.state == StatementState.FAILED:
            raise RuntimeError(
                f"SQL failed: {resp.status.error and resp.status.error.message}"
            )

    log.info("Persisted GENIE_SPACE_ID=%s to %s", space_id, table)


def _grant_app_sp_access(w: WorkspaceClient, space_id: str, app_name: str = "site-selection-accelerator") -> None:
    """Grant the Databricks App's service principal CAN_RUN on the Genie Space."""
    try:
        app = w.apps.get(app_name)
        sp_client_id = app.service_principal_client_id
        if not sp_client_id:
            log.warning("App %s has no service_principal_client_id", app_name)
            return

        _api(w, "PATCH", f"/api/2.0/permissions/genie/{space_id}", {
            "access_control_list": [
                {
                    "service_principal_name": sp_client_id,
                    "permission_level": "CAN_RUN",
                }
            ],
        })
        log.info("Granted CAN_RUN on Genie Space %s to SP %s", space_id, sp_client_id)
    except Exception as e:
        log.warning("Could not grant SP access to Genie Space: %s", e)


def _grant_app_sp_schema_access(
    w: WorkspaceClient,
    catalog: str,
    schema: str,
    warehouse_id: str,
    app_name: str = "site-selection-accelerator",
) -> None:
    """Grant the app service principal catalog/schema access plus volume read/write."""
    from databricks.sdk.service.sql import StatementState

    try:
        app = w.apps.get(app_name)
        sp_id = app.service_principal_id
        if not sp_id:
            log.warning("App %s has no service_principal_id — skipping schema grants", app_name)
            return

        sps = list(w.service_principals.list(filter=f"id eq {sp_id}"))
        if not sps:
            log.warning("Could not resolve service principal %s", sp_id)
            return
        sp_display_name = sps[0].display_name

        grants = [
            f"GRANT USE CATALOG ON CATALOG `{catalog}` TO `{sp_display_name}`",
            f"GRANT USE SCHEMA ON SCHEMA `{catalog}`.`{schema}` TO `{sp_display_name}`",
            f"GRANT SELECT ON SCHEMA `{catalog}`.`{schema}` TO `{sp_display_name}`",
            f"GRANT MODIFY ON SCHEMA `{catalog}`.`{schema}` TO `{sp_display_name}`",
            # Model volume (read) and the Save Analysis staging volume (write)
            f"GRANT READ VOLUME ON SCHEMA `{catalog}`.`{schema}` TO `{sp_display_name}`",
            f"GRANT WRITE VOLUME ON SCHEMA `{catalog}`.`{schema}` TO `{sp_display_name}`",
        ]
        for stmt in grants:
            resp = w.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=stmt,
            )
            if resp.status and resp.status.state == StatementState.FAILED:
                err_msg = resp.status.error.message if resp.status.error else "unknown"
                log.warning("Grant failed: %s — %s", stmt, err_msg)
            else:
                log.info("Executed: %s", stmt)
    except Exception as e:
        log.warning("Could not grant schema access to app SP: %s", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Main

# COMMAND ----------

def main(catalog: str, schema: str, warehouse_id: str) -> str:
    """Ensure the Genie Space exists, update configuration, and return its ID."""
    w = WorkspaceClient()

    existing_tables = _discover_existing_tables(w, warehouse_id, catalog, schema)

    space_id = _find_existing_space(w)
    if space_id:
        _update_space(w, space_id, catalog, schema, existing_tables)
    else:
        space_id = _create_space(w, catalog, schema, warehouse_id, existing_tables)

    _grant_app_sp_access(w, space_id)
    _grant_app_sp_schema_access(w, catalog, schema, warehouse_id)
    _persist_space_id(w, catalog, schema, space_id, warehouse_id)
    return space_id

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute

# COMMAND ----------

logging.basicConfig(level=logging.INFO)

sid = main(catalog, schema, warehouse_id)
print(f"GENIE_SPACE_ID={sid}")
