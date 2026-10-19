# Live app run (Databricks App API)

_Captured 2026-10-19 17:03:55 UTC by `scripts/capture_evidence.py`._

- **App:** https://site-selection-accelerator-7474660412302141.aws.databricksapps.com
- **Request:** brand `Pret A Manger` → London, GB (H3 res 9, competition β=1.0, catchment 0.8 km)
- **Session:** `1a14ed6518aa` · **end-to-end time:** 173.7s
- **Saved to Delta:** analysis_id `e827d731-8e91-4f53-b873-f611c99e0e02` → geo_sme_emea_catalog.site_selection.analyses, geo_sme_emea_catalog.site_selection.analysis_brand_profiles, geo_sme_emea_catalog.site_selection.analysis_hexagons, geo_sme_emea_catalog.site_selection.analysis_competitors, geo_sme_emea_catalog.site_selection.analysis_fingerprints
- **Hexagons scored:** 14,551 · existing brand cells: 262 · candidates with ≥50% cannibalization: 1,527 (10.7%)

## Progress stream (SSE)

```
   0.0s  starting
   0.0s  loading_model
   1.8s  resolving_brand
  29.3s  tessellating
  31.3s  querying_pois
  41.8s  querying_buildings
  47.1s  building_vectors
  47.2s  generating_embeddings
  52.7s  computing_similarity
  52.7s  finding_competitors
  58.6s  caching_results
 145.1s  done
```

## Top 10 candidate cells by opportunity score

| hex_id | address | similarity | opportunity | cannibalization | nearest_own_store_km | competitors |
|---|---|---|---|---|---|---|
| 89194e6f38fffff |  | 0.9739 | 0.9977 | 0 | 2.202 | 0 |
| 89195da48a7ffff | 2nd Floor, 35 Devonshire Pl | 0.9587 | 0.9963 | 0.7467 | 0.32 | 0 |
| 89194ad350bffff | - | 0.9472 | 0.9956 | 0.0653 | 1.367 | 0 |
| 89195da4863ffff | 344 Edgware Rd | 0.9819 | 0.9951 | 0.7467 | 0.321 | 1 |
| 89195da626fffff | 2 Woodberry Grove | 0.9701 | 0.994 | 0 | 3.381 | 1 |
| 89195da546bffff | Unit 9, Spring Villa Park, Spring Villa Rd | 0.9238 | 0.9935 | 0 | 4.896 | 0 |
| 89194ac2283ffff | High Street, Croydon | 0.9556 | 0.993 | 0.4978 | 0.649 | 1 |
| 89195da6ba7ffff | 184 Upper Street | 0.9536 | 0.9929 | 0.7439 | 0.324 | 1 |
| 89194ad2463ffff | Brunel Business Centre Unit 4 | 0.9121 | 0.9927 | 0.7266 | 0.346 | 0 |
| 89194ada5c7ffff | 1-3 Lexham Gardens | 0.9896 | 0.9924 | 0.7466 | 0.321 | 2 |

## Drill-down for the top cell (`/api/results/{session}/hexagon/{hex}`)

> This site has more industrial and service buildings, differing from the brand's typical residential and commercial locations. It lacks typical brand amenities like clothing stores and professional services.

- cannibalization_risk: 0.0 · nearest_store_km: 2.202 · competitors in cell: 0

## Shortlist after adding two cells and moving one to *site visit* (`/api/shortlist`)

| id | hex_id | status | note | similarity | cannibalization_risk | nearest_store_km |
|---|---|---|---|---|---|---|
| 12 | 89195da48a7ffff | candidate |  | 0.9587 | 0.7467 | 0.32 |
| 11 | 89194e6f38fffff | site_visit | Evidence run: top-ranked low-cannibalization cell | 0.9739 | 0 | 2.202 |
