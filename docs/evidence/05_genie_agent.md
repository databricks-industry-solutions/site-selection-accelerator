# Genie Agent over the governed tables

_Captured 2026-10-19 16:37:37 UTC by `scripts/capture_evidence.py`._

- **Genie Space:** `01f1cbd0d7e110528d9682510b884d67` (https://fevm-geo-sme-emea.cloud.databricks.com/genie/rooms/01f1cbd0d7e110528d9682510b884d67)

## Q: How many Pret A Manger locations are there in London?

**Generated SQL**

```sql
WITH city_h3 AS (
  SELECT explode(h3_polyfillash3(`geom_wkt`, 9)) AS `h3_cell`
  FROM `geo_sme_emea_catalog`.`site_selection`.`gold_cities`
  WHERE `country` = 'GB'
    AND `city_name` = 'London'
)
SELECT COUNT(*) AS `pret_a_manger_location_count`
FROM `geo_sme_emea_catalog`.`site_selection`.`gold_places_enriched` p
WHERE h3_longlatash3(p.`lon`, p.`lat`, 9) IN (SELECT `h3_cell` FROM city_h3)
  AND p.`lon` IS NOT NULL
  AND p.`lat` IS NOT NULL
  AND (p.`brand_name_primary` ILIKE '%Pret A Manger%' OR p.`poi_primary_name` ILIKE '%Pret A Manger%')
```

**Result (first 10 rows)**

| pret_a_manger_location_count |
|---|
| 332 |

There are **332** Pret A Manger locations in **London, GB** based on places matched to **Pret A Manger** within the London city boundary. In this result, the total count is **332**.

## Q: Which brands have the most coffee shops in London?

**Generated SQL**

```sql
WITH `city_h3` AS (
  SELECT explode(h3_polyfillash3(`c`.`geom_wkt`, 9)) AS `h3_cell`
  FROM `geo_sme_emea_catalog`.`site_selection`.`gold_cities` `c`
  WHERE `c`.`country` = 'GB'
    AND `c`.`city_name` = 'London'
)
SELECT
  `p`.`brand_name_primary` AS `brand_name_primary`,
  COUNT(*) AS `coffee_shop_count`
FROM `geo_sme_emea_catalog`.`site_selection`.`gold_places_enriched` `p`
WHERE h3_longlatash3(`p`.`lon`, `p`.`lat`, 9) IN (SELECT `h3_cell` FROM `city_h3`)
  AND `p`.`lon` IS NOT NULL
  AND `p`.`lat` IS NOT NULL
  AND `p`.`brand_name_primary` IS NOT NULL
  AND (
    `p`.`basic_category` ILIKE '%coffee%'
    OR `p`.`poi_primary_category` ILIKE '%coffee%'
    OR `p`.`poi_alt_category` ILIKE '%coffee%'
    OR `p`.`poi_primary_taxonomy` ILIKE '%coffee%'
    OR `p`.`poi_alt_taxonomy` ILIKE '%coffee%'
  )
GROUP BY `p`.`brand_name_primary`
ORDER BY `coffee_shop_count` DESC, `p`.`brand_name_primary` ASC
```

**Result (first 10 rows)**

| brand_name_primary | coffee_shop_count |
|---|---|
| Costa Coffee | 343 |
| Starbucks | 194 |
| Caffè Nero | 158 |
| Pret A Manger | 56 |
| Black Sheep Coffee | 35 |
| Costa | 24 |
| WatchHouse | 16 |
| Wild Bean Cafe | 11 |
| SOHO Coffee | 10 |
| Blank Street | 9 |

Examples include:
- **Costa Coffee** — **343** coffee shops
- **Starbucks** — **194**
- **Caffè Nero** — **158**
- **Pret A Manger** — **56**
- **Black Sheep Coffee** — **35**

## Q: For the latest analysis, list the top 10 hexagons by opportunity score with their cannibalization risk and nearest store distance.

**Generated SQL**

```sql
WITH latest_analysis AS (
    SELECT analysis_id
    FROM geo_sme_emea_catalog.site_selection.analyses
    WHERE created_at IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 1
),
ranked AS (
    SELECT h.hex_id, h.opportunity_score, h.cannibalization_risk, h.nearest_store_km,
           h.similarity, h.lat, h.lon, h.address,
           RANK() OVER (ORDER BY h.opportunity_score DESC) AS rnk
    FROM geo_sme_emea_catalog.site_selection.analysis_hexagons h
    JOIN latest_analysis la ON la.analysis_id = h.analysis_id
    WHERE NOT h.is_brand_cell
      AND h.opportunity_score IS NOT NULL
)
SELECT hex_id, opportunity_score, cannibalization_risk, nearest_store_km, similarity, lat, lon, address
FROM ranked
WHERE rnk <= 10
ORDER BY opportunity_score DESC
```

**Result (first 10 rows)**

| hex_id | opportunity_score | cannibalization_risk | nearest_store_km | similarity | lat | lon | address |
|---|---|---|---|---|---|---|---|
| 89194e6f38fffff | 0.9997 | 0.0 | 2.202 | 0.9949 | 51.50670339626138 | 0.14268375870347685 |  |
| 89195da48a7ffff | 0.9975 | 0.7467 | 0.32 | 0.9565 | 51.522710212820435 | -0.14808691299056154 | 2nd Floor, 35 Devonshire Pl |
| 89194ada51bffff | 0.9963 | 0.7466 | 0.321 | 0.9355 | 51.491621033298635 | -0.18939754219274865 | 19 Eastbourne Terrace |
| 89194adb0dbffff | 0.996 | 0.7464 | 0.321 | 0.9344 | 51.51237245173419 | -0.3114815578178395 | 40 Uxbridge Rd |
| 89195da626fffff | 0.9958 | 0.0 | 3.381 | 0.9724 | 51.61135152254947 | -0.17953880432936212 | 2 Woodberry Grove |
| 89194ada5c7ffff | 0.9945 | 0.7466 | 0.321 | 0.9978 | 51.49435048575329 | -0.18774225305579959 | 1-3 Lexham Gardens |
| 89195da4863ffff | 0.9933 | 0.7467 | 0.321 | 0.9402 | 51.52163795401197 | -0.17118195803146605 | 344 Edgware Rd |
| 89194e6ad77ffff | 0.9932 | 0.0 | 2.39 | 0.898 | 51.573072371447054 | 0.14750321745381503 | Office 27, 321-323 High Rd |
| 89194ad350bffff | 0.9931 | 0.0653 | 1.367 | 0.8979 | 51.51395687440407 | -0.0502019349267765 | - |
| 89195da6267ffff | 0.9926 | 0.0 | 3.158 | 0.9291 | 51.611564743132035 | -0.1749119306180032 | 634 High Rd, North Finchley |

The top 10 candidate hexagons from the latest analysis all have very high opportunity scores (ranging from **0.9997** to **0.9926**). Notable examples include:

- **89194e6f38fffff** (near 0.1427, 51.5067): opportunity score **0.9997**, cannibalization risk **0.0**, nearest store **2.2 km** away
- **89195da48a7ffff** (2nd Floor, 35 Devonshire Pl): opportunity score **0.9975**, cannibalization risk **0.7467**, nearest store just **0.32 km** away
- **89194ada51bffff** (19 Eastbourne Terrace): opportunity score **0.9963**, cannibalization risk **0.7466**, nearest store **0.321 km** away
- **89194adb0dbffff** (40 Uxbridge Rd): opportunity score **0.996**, cannibalization risk **0.7464**, nearest store **0.321 km** away
- **89195da626fffff** (2 Woodberry Grove): opportunity score **0.9958**, cannibalization risk **0.0**, nearest store **3.381 km** away

Overall, hexagons located very close to an existing store (around 0.32 km) tend to carry high cannibalization risk (~0.75), while those farther away (2–3.4 km) show no cannibalization risk at all, suggesting a clear trade-off between proximity and overlap with existing locations.
