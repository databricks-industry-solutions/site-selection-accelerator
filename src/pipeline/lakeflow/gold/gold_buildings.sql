-- Gold: buildings with the categorical features Hex2Vec consumes
-- (building type + discretised height band). Liquid clustering on the bbox
-- replaces the old OPTIMIZE ... ZORDER step and is maintained on every refresh.

CREATE OR REFRESH MATERIALIZED VIEW gold_buildings
COMMENT 'Buildings with type/height-band features and a precomputed H3 res-9 cell.'
CLUSTER BY (bbox_xmin, bbox_ymin)
AS SELECT
    building_id,
    building_subtype,
    building_class,
    height,
    num_floors,
    CONCAT('bldg_', COALESCE(building_subtype, building_class, 'other')) AS building_category,
    CASE
        WHEN height IS NULL THEN NULL
        WHEN height <= 6    THEN 'height_low_rise'
        WHEN height <= 15   THEN 'height_mid_rise'
        WHEN height <= 35   THEN 'height_high_rise'
        ELSE                     'height_skyscraper'
    END AS height_bin,
    lon, lat, h3_cell,
    bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax
FROM silver_buildings;
