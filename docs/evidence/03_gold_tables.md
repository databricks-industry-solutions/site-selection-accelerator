# Governed silver/gold tables in Unity Catalog

_Captured 2026-10-19 17:00:14 UTC by `scripts/capture_evidence.py`._

## Row counts

| table_name | row_count |
|---|---|
| silver_places | 77,539,252 |
| silver_buildings | 147,819,228 |
| gold_cities | 117,376 |
| gold_places | 21,738,526 |
| gold_places_enriched | 77,539,252 |
| gold_buildings | 147,819,228 |

## How each city footprint was resolved (`gold_cities.polygon_source`)

| polygon_source | cities |
|---|---|
| locality | 52,770 |
| bbox | 39,815 |
| population_buffer | 13,732 |
| admin_union | 11,059 |

## Sample cities

| country | city_name | population | polygon_source | has_polygon | center_lat | center_lon |
|---|---|---|---|---|---|---|
| GB | London | 8,908,083 | population_buffer | false | 51.5074 | -0.1278 |
| US | New York | 8,467,513 | locality | true | 40.7127 | -74.006 |
| DE | Berlin | 3,769,962 | admin_union | true | 52.5174 | 13.3951 |
| FR | Paris | 2,133,111 | locality | true | 48.8535 | 2.3484 |
| SE | Stockholm | 984,748 | population_buffer | false | 59.3251 | 18.0711 |

## Top model categories in `gold_places`

| category | pois |
|---|---|
| restaurant | 1,917,926 |
| real_estate | 1,665,291 |
| professional_services | 1,428,438 |
| shopping | 1,313,264 |
| beauty_salon | 1,292,782 |
| hotel | 1,237,826 |
| automotive_repair | 969,408 |
| clothing_store | 964,630 |
| grocery_store | 946,891 |
| cafe | 738,292 |
| hair_salon | 718,359 |
| dentist | 684,772 |
