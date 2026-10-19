# Lakeflow Declarative Pipeline — run and data quality

_Captured 2026-10-19 17:00:07 UTC by `scripts/capture_evidence.py`._

- **Pipeline:** `[dev dilshad_shawki] [dev] Site Selection - Overture Medallion Pipeline` (`6280cf95-c3ce-4d8c-8e6c-d3bea041965c`), serverless, triggered by the ETL job
- **Update:** `17f83743-7f09-47ff-9864-1f5c1a71f320` · 2026-10-19T16:38:50.465Z → 2026-10-19T16:39:27.618Z

Bronze is the CARTO Overture Marketplace share (read zero-copy over Delta Sharing); silver and gold are materialized views defined in `src/pipeline/lakeflow/`.

## Recent pipeline updates

| update_id | started | ended | state |
|---|---|---|---|
| 17f83743-7f09-47ff-9864-1f5c1a71f320 | 2026-10-19T16:38:52.441Z | 2026-10-19T16:39:27.618Z | COMPLETED |
| 13591cf0-71b3-401c-9d3c-179d820176d5 | 2026-10-19T15:29:36.162Z | 2026-10-19T15:30:12.383Z | COMPLETED |
| 5b0b4e65-e60a-4439-8e34-27a423dc7529 | 2026-10-19T15:04:20.088Z | 2026-10-19T15:10:21.169Z | COMPLETED |

## Datasets refreshed (update above)

| dataset | output_rows | dropped_rows |
|---|---|---|
| gold_buildings | 147,819,228 | 0 |
| gold_cities | 117,376 | 0 |
| gold_places | 21,738,526 | 0 |
| gold_places_enriched | 77,539,252 | 0 |
| silver_buildings | 147,819,228 | 0 |
| silver_places | 77,539,252 | 978,518 |

## Data-quality expectations

`DROP ROW` expectations remove the row; the others are warn-only and are tracked so drift in Overture's data shows up in the event log.

| dataset | expectation | passed | failed | failed_pct |
|---|---|---|---|---|
| gold_cities | has_city_name | 117,376 | 0 | 0.00% |
| gold_cities | has_geometry | 117,376 | 0 | 0.00% |
| gold_cities | has_polygon | 63,829 | 53,547 | 45.62% |
| gold_cities | valid_bbox | 117,376 | 0 | 0.00% |
| silver_buildings | has_building_id | 147,819,228 | 0 | 0.00% |
| silver_buildings | has_h3_cell | 147,819,228 | 0 | 0.00% |
| silver_buildings | plausible_height | 147,819,228 | 0 | 0.00% |
| silver_buildings | valid_centroid | 147,819,228 | 0 | 0.00% |
| silver_places | confident_match | 63,844,275 | 14,673,495 | 18.69% |
| silver_places | has_address | 74,524,448 | 3,993,322 | 5.09% |
| silver_places | has_name | 78,517,770 | 0 | 0.00% |
| silver_places | has_poi_id | 78,517,770 | 0 | 0.00% |
| silver_places | not_closed | 77,539,252 | 978,518 | 1.25% |
| silver_places | valid_coordinate | 78,517,770 | 0 | 0.00% |
