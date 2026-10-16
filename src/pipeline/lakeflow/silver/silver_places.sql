-- Silver: every categorised Overture POI, flattened out of the CARTO
-- Marketplace share (the bronze layer — read zero-copy over Delta Sharing,
-- so there is no raw copy to maintain). Typed, de-nested, and quality-gated
-- once here so both gold POI tables inherit the same cleaning rules.
--
-- Schema drift is absorbed here too. Overture replaced `categories.primary`
-- with `taxonomy.primary` and renamed a handful of categories; the CASE below
-- maps them back onto the vocabulary the Hex2Vec model was trained on, so a
-- new Overture release doesn't silently zero out model features.
-- (`supermarket` no longer exists — Overture folded it into `grocery_store`.)

CREATE OR REFRESH MATERIALIZED VIEW silver_places (
  CONSTRAINT has_poi_id       EXPECT (poi_id IS NOT NULL)                         ON VIOLATION DROP ROW,
  CONSTRAINT valid_coordinate EXPECT (lon BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) ON VIOLATION DROP ROW,
  CONSTRAINT has_name         EXPECT (poi_primary_name IS NOT NULL),
  CONSTRAINT has_address      EXPECT (address_line IS NOT NULL),
  CONSTRAINT not_closed       EXPECT (operating_status IS NULL OR operating_status <> 'permanently_closed') ON VIOLATION DROP ROW,
  CONSTRAINT confident_match  EXPECT (confidence >= 0.5)
)
COMMENT 'Cleaned Overture POIs (all categories) with names, brands, addresses and coordinates.'
CLUSTER BY (bbox_xmin, bbox_ymin)
AS SELECT
    p.id                                                AS poi_id,
    p.names.primary                                     AS poi_primary_name,
    concat_ws(', ', map_values(p.names.common))         AS poi_common_name,
    CASE p.taxonomy.primary
        WHEN 'food_truck_stand'       THEN 'food_truck'
        WHEN 'dental_clinic'          THEN 'dentist'
        WHEN 'general_dentistry'      THEN 'dentist'
        WHEN 'professional_service'   THEN 'professional_services'
        WHEN 'real_estate_agent'      THEN 'real_estate'
        WHEN 'real_estate_service'    THEN 'real_estate'
        WHEN 'commercial_real_estate' THEN 'real_estate'
        ELSE p.taxonomy.primary
    END                                                 AS category,
    p.taxonomy.primary                                  AS overture_category,
    p.basic_category                                    AS overture_basic_category,
    concat_ws(', ', p.taxonomy.alternates)              AS alt_categories,
    NULLIF(p.operating_status, '')                      AS operating_status,
    p.brand.names.primary                               AS brand_name_primary,
    concat_ws(', ', map_values(p.brand.names.common))   AS brand_name_common,
    p.addresses[0].freeform                             AS address_line,
    p.addresses[0].locality                             AS locality,
    p.addresses[0].postcode                             AS postcode,
    p.addresses[0].region                               AS region,
    p.addresses[0].country                              AS country,
    p.confidence                                        AS confidence,
    ST_X(p.geom)                        AS lon,
    ST_Y(p.geom)                        AS lat,
    CAST(p.bbox.xmin AS DOUBLE)                         AS bbox_xmin,
    CAST(p.bbox.xmax AS DOUBLE)                         AS bbox_xmax,
    CAST(p.bbox.ymin AS DOUBLE)                         AS bbox_ymin,
    CAST(p.bbox.ymax AS DOUBLE)                         AS bbox_ymax
FROM ${carto_places_catalog}.carto.place p
WHERE p.taxonomy.primary IS NOT NULL;
