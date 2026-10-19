# ETL job run (Lakeflow Jobs)

_Captured 2026-10-19 15:43:08 UTC by `scripts/capture_evidence.py`._

- **Job:** `[dev dilshad_shawki] [dev] Site Selection - Refresh Geospatial Data` (job_id `50034938189224`)
- **Run:** `389883439182301` — [https://fevm-geo-sme-emea.cloud.databricks.com/?o=7474660412302141#job/50034938189224/run/389883439182301](https://fevm-geo-sme-emea.cloud.databricks.com/?o=7474660412302141#job/50034938189224/run/389883439182301)
- **Result:** **SUCCESS**
- **Started:** 2026-10-19 15:29:10 UTC · **Wall time:** 12m 44s

## Tasks

| task | type | result | start | duration |
|---|---|---|---|---|
| setup_schema | notebook | SUCCESS | 2026-10-19 15:29:10 UTC | 0m 22s |
| create_analysis_tables | notebook | SUCCESS | 2026-10-19 15:29:32 UTC | 0m 10s |
| refresh_gold_pipeline | pipeline | SUCCESS | 2026-10-19 15:29:33 UTC | 0m 52s |
| create_gold_radiance | notebook | SUCCESS | 2026-10-19 15:30:25 UTC | 10m 26s |
| train_hex2vec | notebook | SUCCESS | 2026-10-19 15:30:25 UTC | 11m 18s |
| setup_genie_space | notebook | SUCCESS | 2026-10-19 15:40:52 UTC | 1m 02s |
