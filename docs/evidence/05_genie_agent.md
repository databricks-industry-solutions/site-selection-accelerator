# Genie Agent over the governed tables

_Captured 2026-10-19 17:05:12 UTC by `scripts/capture_evidence.py`._

- **Genie Space:** `01f1cbd0d7e110528d9682510b884d67` (https://fevm-geo-sme-emea.cloud.databricks.com/genie/rooms/01f1cbd0d7e110528d9682510b884d67)

## Q: How many Pret A Manger locations are there in London?

**Generated SQL**

```sql
WITH `city_h3` AS (
  SELECT explode(h3_polyfillash3(`c`.`geom_wkt`, 9)) AS `h3_cell`
  FROM `geo_sme_emea_catalog`.`site_selection`.`gold_cities` `c`
  WHERE `c`.`country` = 'GB'
    AND `c`.`city_name` = 'London'
)
SELECT COUNT(*) AS `pret_a_manger_location_count`
FROM `geo_sme_emea_catalog`.`site_selection`.`gold_places_enriched` `p`
WHERE h3_longlatash3(`p`.`lon`, `p`.`lat`, 9) IN (SELECT `h3_cell` FROM `city_h3`)
  AND (`p`.`brand_name_primary` ILIKE '%Pret A Manger%' OR `p`.`poi_primary_name` ILIKE '%Pret A Manger%')
  AND `p`.`lon` IS NOT NULL
  AND `p`.`lat` IS NOT NULL
```

**Result (first 10 rows)**

| pret_a_manger_location_count |
|---|
| 332 |

There are **332** Pret A Manger locations in **London, GB** based on places matched to **brand_name_primary** or **poi_primary_name** containing “Pret A Manger” within the London city boundary.

## Q: Which brands have the most coffee shops in London?

**Generated SQL**

```sql
WITH city_h3 AS (
  SELECT explode(h3_polyfillash3(`geom_wkt`, 9)) AS `h3_cell`
  FROM `geo_sme_emea_catalog`.`site_selection`.`gold_cities`
  WHERE `country` = 'GB'
    AND `city_name` = 'London'
), brand_counts AS (
  SELECT
    `p`.`brand_name_primary` AS `brand_name_primary`,
    COUNT(*) AS `coffee_shop_count`
  FROM `geo_sme_emea_catalog`.`site_selection`.`gold_places_enriched` `p`
  WHERE h3_longlatash3(`p`.`lon`, `p`.`lat`, 9) IN (SELECT `h3_cell` FROM city_h3)
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
)
SELECT
  `brand_name_primary`,
  `coffee_shop_count`,
  RANK() OVER (ORDER BY `coffee_shop_count` DESC) AS `brand_rank`
FROM brand_counts
ORDER BY `coffee_shop_count` DESC, `brand_name_primary` ASC
```

**Result (first 10 rows)**

| brand_name_primary | coffee_shop_count | brand_rank |
|---|---|---|
| Costa Coffee | 343 | 1 |
| Starbucks | 194 | 2 |
| Caffè Nero | 158 | 3 |
| Pret A Manger | 56 | 4 |
| Black Sheep Coffee | 35 | 5 |
| Costa | 24 | 6 |
| WatchHouse | 16 | 7 |
| Wild Bean Cafe | 11 | 8 |
| SOHO Coffee | 10 | 9 |
| Blank Street | 9 | 10 |

Examples include:
- **Costa Coffee** — **343** coffee shops
- **Starbucks** — **194**
- **Caffè Nero** — **158**
- **Pret A Manger** — **56**
- **Black Sheep Coffee** — **35**

Would you prefer to count only locations where coffee is the primary category, rather than including places where it's just a secondary or alternate category?

## Q: For the latest analysis, list the top 10 hexagons by opportunity score with their cannibalization risk and nearest store distance.

**Generated SQL**

```sql
WITH `latest_analysis` AS (
  SELECT `analysis_id`
  FROM `geo_sme_emea_catalog`.`site_selection`.`analyses`
  WHERE `created_at` IS NOT NULL
  ORDER BY `created_at` DESC, `analysis_id` DESC
  LIMIT 1
)
SELECT
  h.`hex_id`,
  h.`opportunity_score`,
  h.`cannibalization_risk`,
  h.`nearest_store_km`
FROM `geo_sme_emea_catalog`.`site_selection`.`analysis_hexagons` h
INNER JOIN `latest_analysis` l
  ON h.`analysis_id` = l.`analysis_id`
WHERE h.`is_brand_cell` = false
  AND h.`opportunity_score` IS NOT NULL
  AND h.`cannibalization_risk` IS NOT NULL
  AND h.`nearest_store_km` IS NOT NULL
ORDER BY h.`opportunity_score` DESC, h.`hex_id` ASC
LIMIT 10
```

**Result (first 10 rows)**

| hex_id | opportunity_score | cannibalization_risk | nearest_store_km |
|---|---|---|---|
| 89194e6f38fffff | 0.9977 | 0.0 | 2.202 |
| 89195da48a7ffff | 0.9963 | 0.7467 | 0.32 |
| 89194ad350bffff | 0.9956 | 0.0653 | 1.367 |
| 89195da4863ffff | 0.9951 | 0.7467 | 0.321 |
| 89195da626fffff | 0.994 | 0.0 | 3.381 |
| 89195da546bffff | 0.9935 | 0.0 | 4.896 |
| 89194ac2283ffff | 0.993 | 0.4978 | 0.649 |
| 89195da6ba7ffff | 0.9929 | 0.7439 | 0.324 |
| 89194ad2463ffff | 0.9927 | 0.7266 | 0.346 |
| 89194ada5c7ffff | 0.9924 | 0.7466 | 0.321 |

Here are the **top 10 candidate hexagons** from the latest analysis ranked by opportunity score; the data below is the full set returned.

- **89194e6f38fffff** — opportunity score **0.9977**, cannibalization risk **0.0**, nearest store **2.202 km**
- **89195da48a7ffff** — opportunity score **0.9963**, cannibalization risk **0.7467**, nearest store **0.32 km**
- **89194ad350bffff** — opportunity score **0.9956**, cannibalization risk **0.0653**, nearest store **1.367 km**
- **89195da4863ffff** — opportunity score **0.9951**, cannibalization risk **0.7467**, nearest store **0.321 km**
- **89195da626fffff** — opportunity score **0.9940**, cannibalization risk **0.0**, nearest store **3.381 km**

Across all 10 returned hexagons, opportunity scores are tightly clustered between **0.9924** and **0.9977**, while cannibalization risk ranges from **0.0** to **0.7467** and nearest store distance ranges from **0.32 km** to **4.896 km**.
