# Lakebase operational store

_Captured 2026-10-19 16:33:24 UTC by `scripts/capture_evidence.py`._

- **Project:** `projects/site-selection-dev` · branch `production` · endpoint `projects/site-selection-dev/branches/production/endpoints/primary`
- Queried directly with a short-lived OAuth credential (`w.postgres.generate_database_credential`).

## Tables in the app-owned `site_selection` schema

| table_name | approx_rows |
|---|---|
| session_hexagons | 72,755 |
| sessions | 5 |
| shortlist | 10 |

## Most recent sessions (write-through from the app)

| session_id | created_at | brand | city | n_hexagons | payload |
|---|---|---|---|---|---|
| 42c85d45ec08 | 2026-10-19 16:30:49.995867+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| 9f8904a5634f | 2026-10-19 16:24:24.963900+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| 805b48325864 | 2026-10-19 16:16:27.382104+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| 10c58b21f320 | 2026-10-19 16:11:53.345226+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| e485d4c5e76a | 2026-10-19 15:45:35.420801+00:00 | Pret A Manger | London | 14,551 | 1814 kB |

## Top-5 lookup for the evidence session (25 ms round-trip from laptop)

| hex_id | opportunity | cannibalization | nearest_store_km |
|---|---|---|---|
| 89194e6f38fffff | 0.9997 | 0.000 | 2.202 |
| 89195da48a7ffff | 0.9975 | 0.747 | 0.32 |
| 89194ada51bffff | 0.9963 | 0.747 | 0.321 |
| 89194adb0dbffff | 0.9960 | 0.746 | 0.321 |
| 89195da626fffff | 0.9958 | 0.000 | 3.381 |

## Shortlist rows

| id | hex_id | status | note | updated_at |
|---|---|---|---|---|
| 10 | 89195da48a7ffff | candidate |  | 2026-10-19 16:32:45.231062+00:00 |
| 9 | 89194e6f38fffff | site_visit | Evidence run: top-ranked low-cannibalization cell | 2026-10-19 16:32:45.177656+00:00 |
| 8 | 89195da48a7ffff | candidate |  | 2026-10-19 16:26:20.019204+00:00 |
| 7 | 89194e6f38fffff | site_visit | Evidence run: top-ranked low-cannibalization cell | 2026-10-19 16:26:19.966102+00:00 |
| 6 | 89195da48a7ffff | candidate |  | 2026-10-19 16:18:23.740813+00:00 |
