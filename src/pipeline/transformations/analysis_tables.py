# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # Analysis Result Tables
# MAGIC Creates append-only tables for persisting app analysis outputs.
# MAGIC Each analysis run has a unique `analysis_id` so that multiple
# MAGIC analyses (different brands, cities, parameters) coexist.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("schema", "")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

print(f"Catalog: {catalog}")
print(f"Schema:  {schema}")

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS IDENTIFIER('${catalog}' || '.' || '${schema}' || '.analyses') (
# MAGIC     analysis_id          STRING    NOT NULL,
# MAGIC     session_id           STRING    NOT NULL,
# MAGIC     brand_input_mode     STRING,
# MAGIC     brand_input_value    STRING,
# MAGIC     country              STRING,
# MAGIC     city                 STRING,
# MAGIC     h3_resolution        INT,
# MAGIC     categories           STRING,
# MAGIC     enable_competition   BOOLEAN,
# MAGIC     beta                 DOUBLE,
# MAGIC     include_buildings    BOOLEAN,
# MAGIC     city_polygon_geojson STRING,
# MAGIC     center_lat           DOUBLE,
# MAGIC     center_lon           DOUBLE,
# MAGIC     created_at           TIMESTAMP,
# MAGIC     created_by           STRING
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS IDENTIFIER('${catalog}' || '.' || '${schema}' || '.analysis_brand_profiles') (
# MAGIC     analysis_id      STRING NOT NULL,
# MAGIC     category         STRING,
# MAGIC     avg_count        DOUBLE,
# MAGIC     pct_within_type  DOUBLE,
# MAGIC     feature_type     STRING,
# MAGIC     group_name       STRING
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS IDENTIFIER('${catalog}' || '.' || '${schema}' || '.analysis_hexagons') (
# MAGIC     analysis_id       STRING  NOT NULL,
# MAGIC     h3_cell           BIGINT,
# MAGIC     hex_id            STRING,
# MAGIC     similarity        DOUBLE,
# MAGIC     opportunity_score DOUBLE,
# MAGIC     is_brand_cell     BOOLEAN,
# MAGIC     lat               DOUBLE,
# MAGIC     lon               DOUBLE,
# MAGIC     address           STRING,
# MAGIC     poi_count         INT,
# MAGIC     competitor_count  INT,
# MAGIC     top_competitors   STRING,
# MAGIC     cannibalization_risk DOUBLE,
# MAGIC     nearest_store_km     DOUBLE
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS IDENTIFIER('${catalog}' || '.' || '${schema}' || '.analysis_fingerprints') (
# MAGIC     analysis_id          STRING NOT NULL,
# MAGIC     hex_id               STRING,
# MAGIC     category             STRING,
# MAGIC     group_name           STRING,
# MAGIC     feature_type         STRING,
# MAGIC     this_location        DOUBLE,
# MAGIC     brand_average        DOUBLE,
# MAGIC     this_location_pct    DOUBLE,
# MAGIC     brand_average_pct    DOUBLE,
# MAGIC     explanation_summary  STRING
# MAGIC ) USING DELTA

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS IDENTIFIER('${catalog}' || '.' || '${schema}' || '.analysis_competitors') (
# MAGIC     analysis_id STRING NOT NULL,
# MAGIC     hex_id      STRING,
# MAGIC     poi_name    STRING,
# MAGIC     category    STRING,
# MAGIC     brand       STRING,
# MAGIC     address     STRING
# MAGIC ) USING DELTA
