-- Gold: city lookup with polygon, centre and bounding box, so the app never
-- touches raw WKB division geometry.
-- Polygon resolution: the locality's own area first; if Overture has none,
-- ST_Union of every same-name region/county/neighbourhood/macrohood area
-- (covers city-states and metro areas); failing that, a circle sized from the
-- city's population at an assumed 5,000 residents/km² (typical of large
-- European cores — Greater London is ~5,700); and only when population is
-- unknown, a ±0.15° box. Overture ships some major cities (London,
-- Stockholm, Reykjavík) as bare points, and a fixed box badly under- or
-- over-covers them, which skews every hexagon score in the city.
-- `polygon_source` records which rule produced the footprint.
-- Overture now ships native GEOMETRY, so the old WKB round-trips and the
-- REDUCE-based pairwise union collapse into a single ST_Union_Agg.
-- `has_polygon` is a warn-only expectation so the event log records how many
-- cities fall back to the box rather than silently degrading.

CREATE OR REFRESH MATERIALIZED VIEW gold_cities (
  CONSTRAINT has_city_name   EXPECT (city_name IS NOT NULL AND country IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT has_geometry    EXPECT (geom_wkt IS NOT NULL)                         ON VIOLATION DROP ROW,
  CONSTRAINT valid_bbox      EXPECT (bbox_xmin <= bbox_xmax AND bbox_ymin <= bbox_ymax) ON VIOLATION DROP ROW,
  CONSTRAINT has_polygon     EXPECT (has_polygon)
)
COMMENT 'One row per Overture city/town: polygon WKT, centre and bbox for H3 polyfill.'
CLUSTER BY (country, city_name)
AS
WITH localities AS (
    SELECT
        d.id,
        d.country,
        d.names.primary  AS city_name,
        d.population,
        d.bbox
    FROM ${carto_divisions_catalog}.carto.division d
    WHERE d.subtype = 'locality'
        AND d.class IN ('city', 'town')
        AND d.country IS NOT NULL
        AND d.names.primary IS NOT NULL
),
locality_area AS (
    SELECT l.id, FIRST(da.geom) AS geom
    FROM localities l
    INNER JOIN ${carto_divisions_catalog}.carto.division_area da
        ON da.division_id = l.id
    GROUP BY l.id
),
cities_needing_fallback AS (
    SELECT DISTINCT l.city_name, l.country
    FROM localities l
    LEFT JOIN locality_area la ON la.id = l.id
    WHERE la.geom IS NULL
),
fallback_area AS (
    SELECT
        cn.city_name,
        cn.country,
        ST_Union_Agg(da.geom) AS geom
    FROM cities_needing_fallback cn
    INNER JOIN ${carto_divisions_catalog}.carto.division d
        ON d.names.primary = cn.city_name AND d.country = cn.country
    INNER JOIN ${carto_divisions_catalog}.carto.division_area da
        ON da.division_id = d.id
    WHERE d.subtype IN ('region', 'county', 'neighborhood', 'macrohood')
    GROUP BY cn.city_name, cn.country
),
resolved AS (
    SELECT
        l.*,
        CASE
            WHEN la.geom IS NOT NULL THEN 'locality'
            WHEN fa.geom IS NOT NULL THEN 'admin_union'
            WHEN l.population > 0    THEN 'population_buffer'
            ELSE 'bbox'
        END AS polygon_source,
        COALESCE(la.geom, fa.geom) AS geom,
        COALESCE(
            la.geom,
            fa.geom,
            -- Buffer in Web Mercator, scaling the radius by 1/cos(lat) so the
            -- circle is true-distance on the ground, then back to WGS84.
            CASE WHEN l.population > 0 THEN ST_Transform(
                ST_Buffer(
                    ST_Transform(ST_Point(l.bbox.xmin, l.bbox.ymin, 4326), 3857),
                    1000 * SQRT(l.population / 5000.0 / PI()) / COS(RADIANS(l.bbox.ymin))
                ),
                4326
            ) END
        ) AS footprint
    FROM localities l
    LEFT JOIN locality_area la ON la.id = l.id
    LEFT JOIN fallback_area fa
        ON fa.city_name = l.city_name AND fa.country = l.country
)
SELECT
    r.country,
    r.city_name,
    CAST(r.bbox.xmin AS DOUBLE)                              AS center_lon,
    CAST(r.bbox.ymin AS DOUBLE)                              AS center_lat,
    r.population,
    r.geom IS NOT NULL                                       AS has_polygon,
    r.polygon_source,
    COALESCE(
        ST_AsText(r.footprint),
        CONCAT(
            'POLYGON((',
            CAST(r.bbox.xmin - 0.15 AS STRING), ' ', CAST(r.bbox.ymin - 0.15 AS STRING), ', ',
            CAST(r.bbox.xmin + 0.15 AS STRING), ' ', CAST(r.bbox.ymin - 0.15 AS STRING), ', ',
            CAST(r.bbox.xmin + 0.15 AS STRING), ' ', CAST(r.bbox.ymin + 0.15 AS STRING), ', ',
            CAST(r.bbox.xmin - 0.15 AS STRING), ' ', CAST(r.bbox.ymin + 0.15 AS STRING), ', ',
            CAST(r.bbox.xmin - 0.15 AS STRING), ' ', CAST(r.bbox.ymin - 0.15 AS STRING),
            '))'
        )
    )                                                        AS geom_wkt,
    COALESCE(
        CAST(ST_XMin(r.footprint) AS DOUBLE),
        CAST(r.bbox.xmin - 0.15 AS DOUBLE)
    )                                                        AS bbox_xmin,
    COALESCE(
        CAST(ST_XMax(r.footprint) AS DOUBLE),
        CAST(r.bbox.xmin + 0.15 AS DOUBLE)
    )                                                        AS bbox_xmax,
    COALESCE(
        CAST(ST_YMin(r.footprint) AS DOUBLE),
        CAST(r.bbox.ymin - 0.15 AS DOUBLE)
    )                                                        AS bbox_ymin,
    COALESCE(
        CAST(ST_YMax(r.footprint) AS DOUBLE),
        CAST(r.bbox.ymin + 0.15 AS DOUBLE)
    )                                                        AS bbox_ymax
FROM resolved r
;
