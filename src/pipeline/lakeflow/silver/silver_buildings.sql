-- Silver: Overture building footprints reduced to a typed centroid + H3 cell.
-- Footprint geometry is dropped here on purpose: the model only needs counts
-- per hexagon, and carrying ~140M polygons into gold would multiply storage
-- and scan cost for no analytical gain.

CREATE OR REFRESH MATERIALIZED VIEW silver_buildings (
  CONSTRAINT has_building_id  EXPECT (building_id IS NOT NULL)                    ON VIOLATION DROP ROW,
  CONSTRAINT valid_centroid   EXPECT (lon BETWEEN -180 AND 180 AND lat BETWEEN -90 AND 90) ON VIOLATION DROP ROW,
  CONSTRAINT has_h3_cell      EXPECT (h3_cell IS NOT NULL)                        ON VIOLATION DROP ROW,
  CONSTRAINT plausible_height EXPECT (height IS NULL OR height BETWEEN 0 AND 900)
)
COMMENT 'Cleaned Overture buildings: type, height, centroid and H3 res-9 cell.'
AS SELECT
    building_id, building_subtype, building_class, height, num_floors,
    lon, lat, h3_longlatash3(lon, lat, 9) AS h3_cell,
    bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax
FROM (
    SELECT
        b.id                                            AS building_id,
        b.subtype                                       AS building_subtype,
        b.class                                         AS building_class,
        b.height                                        AS height,
        b.num_floors                                    AS num_floors,
        ST_X(ST_Centroid(b.geom))       AS lon,
        ST_Y(ST_Centroid(b.geom))       AS lat,
        CAST(b.bbox.xmin AS DOUBLE)                     AS bbox_xmin,
        CAST(b.bbox.xmax AS DOUBLE)                     AS bbox_xmax,
        CAST(b.bbox.ymin AS DOUBLE)                     AS bbox_ymin,
        CAST(b.bbox.ymax AS DOUBLE)                     AS bbox_ymax
    FROM ${carto_buildings_catalog}.carto.building b
    WHERE b.subtype IS NOT NULL OR b.class IS NOT NULL
);
