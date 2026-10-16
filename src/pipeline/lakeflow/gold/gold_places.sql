-- Gold: POIs restricted to the categories the Hex2Vec model was trained on.
-- Column names are the contract the app and training notebook read.

CREATE OR REFRESH MATERIALIZED VIEW gold_places
COMMENT 'POIs in the accelerator category set, used for Hex2Vec features and app scoring.'
CLUSTER BY (bbox_xmin, bbox_ymin)
AS SELECT
    poi_id,
    category,
    lon,
    lat,
    address_line AS address,
    bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax
FROM silver_places
WHERE category IN (
    'restaurant', 'fast_food_restaurant', 'cafe', 'coffee_shop',
    'bar', 'bakery', 'food_truck',
    'clothing_store', 'convenience_store', 'grocery_store', 'shopping',
    'furniture_store', 'supermarket', 'shopping_mall', 'department_store',
    'bank', 'pharmacy', 'gas_station', 'gym', 'hospital', 'dentist',
    'hair_salon', 'beauty_salon', 'automotive_repair',
    'movie_theater', 'park', 'hotel', 'museum',
    'professional_services', 'real_estate', 'education', 'school'
);
