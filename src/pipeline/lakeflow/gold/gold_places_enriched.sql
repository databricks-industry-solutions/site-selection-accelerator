-- Gold: all categorised POIs with brand names and addresses, shaped for the
-- Genie Space and competitor lookups (brand matching needs every category,
-- not just the model's feature set).

CREATE OR REFRESH MATERIALIZED VIEW gold_places_enriched
COMMENT 'All categorised POIs with brand, name and address fields — the Genie Space and competition-analysis table.'
CLUSTER BY (bbox_xmin, bbox_ymin)
AS SELECT
    poi_id,
    poi_primary_name,
    poi_common_name,
    category        AS basic_category,
    category        AS poi_primary_category,
    alt_categories  AS poi_alt_category,
    category        AS poi_primary_taxonomy,
    alt_categories  AS poi_alt_taxonomy,
    brand_name_primary,
    brand_name_common,
    address_line,
    locality,
    postcode,
    region,
    country,
    confidence,
    lon, lat,
    bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax
FROM silver_places;
