# Live app run (Databricks App API)

_Captured 2026-10-19 16:33:23 UTC by `scripts/capture_evidence.py`._

- **App:** https://site-selection-accelerator-7474660412302141.aws.databricksapps.com
- **Request:** brand `Pret A Manger` → London, GB (H3 res 9, competition β=1.0, catchment 0.8 km)
- **Session:** `42c85d45ec08` · **end-to-end time:** 161.4s
- **Saved to Delta:** analysis_id `82242033-67de-4e9c-bf42-aa5194471aa2` → geo_sme_emea_catalog.site_selection.analyses, geo_sme_emea_catalog.site_selection.analysis_brand_profiles, geo_sme_emea_catalog.site_selection.analysis_hexagons, geo_sme_emea_catalog.site_selection.analysis_competitors, geo_sme_emea_catalog.site_selection.analysis_fingerprints
- **Hexagons scored:** 14,551 · existing brand cells: 262 · candidates with ≥50% cannibalization: 1,527 (10.7%)

## Progress stream (SSE)

```
   0.0s  starting
   3.9s  loading_model
   5.3s  resolving_brand
  32.3s  tessellating
  33.4s  querying_pois
  34.1s  querying_buildings
  36.6s  building_vectors
  36.7s  generating_embeddings
  42.7s  computing_similarity
  42.7s  finding_competitors
  47.4s  caching_results
 132.3s  done
```

## Top 10 candidate cells by opportunity score

| hex_id | address | similarity | opportunity | cannibalization | nearest_own_store_km | competitors |
|---|---|---|---|---|---|---|
| 89194e6f38fffff |  | 0.9949 | 0.9997 | 0 | 2.202 | 0 |
| 89195da48a7ffff | 2nd Floor, 35 Devonshire Pl | 0.9565 | 0.9975 | 0.7467 | 0.32 | 0 |
| 89194ada51bffff | 19 Eastbourne Terrace | 0.9355 | 0.9963 | 0.7466 | 0.321 | 0 |
| 89194adb0dbffff | 40 Uxbridge Rd | 0.9344 | 0.996 | 0.7464 | 0.321 | 0 |
| 89195da626fffff | 2 Woodberry Grove | 0.9724 | 0.9958 | 0 | 3.381 | 1 |
| 89194ada5c7ffff | 1-3 Lexham Gardens | 0.9978 | 0.9945 | 0.7466 | 0.321 | 2 |
| 89195da4863ffff | 344 Edgware Rd | 0.9402 | 0.9933 | 0.7467 | 0.321 | 1 |
| 89194e6ad77ffff | Office 27, 321-323 High Rd | 0.898 | 0.9932 | 0 | 2.39 | 0 |
| 89194ad350bffff | - | 0.8979 | 0.9931 | 0.0653 | 1.367 | 0 |
| 89195da6267ffff | 634 High Rd, North Finchley | 0.9291 | 0.9926 | 0 | 3.158 | 1 |

## Drill-down for the top cell (`/api/results/{session}/hexagon/{hex}`)

> This site has more industrial and service buildings, differing from the brand's typical residential and commercial locations. It lacks typical brand amenities like clothing stores and professional services.

- cannibalization_risk: 0.0 · nearest_store_km: 2.202 · competitors in cell: 0

## Shortlist after adding two cells and moving one to *site visit* (`/api/shortlist`)

| id | hex_id | status | note | similarity | cannibalization_risk | nearest_store_km |
|---|---|---|---|---|---|---|
| 10 | 89195da48a7ffff | candidate |  | 0.9565 | 0.7467 | 0.32 |
| 9 | 89194e6f38fffff | site_visit | Evidence run: top-ranked low-cannibalization cell | 0.9949 | 0 | 2.202 |
