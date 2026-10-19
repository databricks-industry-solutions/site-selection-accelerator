# Lakebase operational store

_Captured 2026-10-19 17:03:56 UTC by `scripts/capture_evidence.py`._

- **Project:** `projects/site-selection-dev` · branch `production` · endpoint `projects/site-selection-dev/branches/production/endpoints/primary`
- Queried directly with a short-lived OAuth credential (`w.postgres.generate_database_credential`).

## Tables in the app-owned `site_selection` schema

| table_name | approx_rows |
|---|---|
| session_hexagons | 87,306 |
| sessions | 6 |
| shortlist | 12 |

## Most recent sessions (write-through from the app)

| session_id | created_at | brand | city | n_hexagons | payload |
|---|---|---|---|---|---|
| 1a14ed6518aa | 2026-10-19 17:01:16.092420+00:00 | Pret A Manger | London | 14,551 | 1650 kB |
| 42c85d45ec08 | 2026-10-19 16:30:49.995867+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| 9f8904a5634f | 2026-10-19 16:24:24.963900+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| 805b48325864 | 2026-10-19 16:16:27.382104+00:00 | Pret A Manger | London | 14,551 | 1702 kB |
| 10c58b21f320 | 2026-10-19 16:11:53.345226+00:00 | Pret A Manger | London | 14,551 | 1702 kB |

## Top-5 lookup for the evidence session (31 ms round-trip from laptop)

| hex_id | opportunity | cannibalization | nearest_store_km |
|---|---|---|---|
| 89194e6f38fffff | 0.9977 | 0.000 | 2.202 |
| 89195da48a7ffff | 0.9963 | 0.747 | 0.32 |
| 89194ad350bffff | 0.9956 | 0.065 | 1.367 |
| 89195da4863ffff | 0.9951 | 0.747 | 0.321 |
| 89195da626fffff | 0.9940 | 0.000 | 3.381 |

## Shortlist rows

| id | hex_id | status | note | updated_at |
|---|---|---|---|---|
| 12 | 89195da48a7ffff | candidate |  | 2026-10-19 17:03:13.638982+00:00 |
| 11 | 89194e6f38fffff | site_visit | Evidence run: top-ranked low-cannibalization cell | 2026-10-19 17:03:13.581249+00:00 |
| 10 | 89195da48a7ffff | candidate |  | 2026-10-19 16:32:45.231062+00:00 |
| 9 | 89194e6f38fffff | site_visit | Evidence run: top-ranked low-cannibalization cell | 2026-10-19 16:32:45.177656+00:00 |
| 8 | 89195da48a7ffff | candidate |  | 2026-10-19 16:26:20.019204+00:00 |
