# ETL job run (Lakeflow Jobs)

_Captured 2026-10-19 17:00:01 UTC by `scripts/capture_evidence.py`._

- **Job:** `[dev dilshad_shawki] [dev] Site Selection - Refresh Geospatial Data` (job_id `50034938189224`)
- **Run:** `1105961252192204` — [https://fevm-geo-sme-emea.cloud.databricks.com/?o=7474660412302141#job/50034938189224/run/1105961252192204](https://fevm-geo-sme-emea.cloud.databricks.com/?o=7474660412302141#job/50034938189224/run/1105961252192204)
- **Result:** **SUCCESS**
- **Started:** 2026-10-19 16:38:25 UTC · **Wall time:** 19m 33s

## Tasks

| task | type | result | start | duration |
|---|---|---|---|---|
| setup_schema | notebook | SUCCESS | 2026-10-19 16:38:25 UTC | 0m 22s |
| create_analysis_tables | notebook | SUCCESS | 2026-10-19 16:38:48 UTC | 0m 11s |
| refresh_gold_pipeline | pipeline | SUCCESS | 2026-10-19 16:38:48 UTC | 0m 42s |
| create_gold_radiance | notebook | SUCCESS | 2026-10-19 16:39:31 UTC | 10m 43s |
| train_hex2vec | notebook | SUCCESS | 2026-10-19 16:39:31 UTC | 18m 27s |
| setup_genie_space | notebook | SUCCESS | 2026-10-19 16:50:15 UTC | 1m 06s |
