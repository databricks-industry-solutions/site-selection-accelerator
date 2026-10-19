# Build notes — decisions, trade-offs and how this was built

This file explains *why* the accelerator looks the way it does. For setup, see
the [README](README.md). For proof that it runs, see
[`docs/evidence/`](docs/evidence/).

## Who this is for

| | Funding executive | Day-to-day owner |
|---|---|---|
| **Typical title** | CFO / Chief Development Officer — signs off new-store capex at the real-estate committee | Head of Real Estate / Director of Site Selection (and their analysts) |
| **What they care about** | Capital at risk per opening. A new site is a multi-year lease plus fit-out, and a poorly chosen one is hard to unwind | How fast they can get from "we want to enter city X" to a defensible shortlist, and how many shortlisted sites survive a site visit |
| **What the build gives them** | A score for each candidate site with its evidence attached (fingerprint, competitors, cannibalization), so the committee sees why a site ranks where it does | One run per city instead of a manual study, a ranked map, and a shortlist with a status workflow that the team works from |

## Architecture in one paragraph

Overture POIs, buildings and admin boundaries arrive from the CARTO
Marketplace listings as zero-copy Delta Sharing catalogs; those are the bronze
layer. A **Lakeflow Spark Declarative Pipeline** builds the silver and gold
layers as materialized views with data-quality expectations. A **Lakeflow Job**
runs the pipeline, provisions the **Genie** space and trains the **Hex2Vec**
model on 37 cities. The model is stored in a UC Volume, and all tables are
governed in **Unity Catalog**. The **Databricks App** (FastAPI + React)
embeds a target city with the pretrained encoder and scores every H3 cell
against the brand's fingerprint. It writes each session and the user's
shortlist to **Lakebase**. *Save Analysis* also writes the run to Delta, so
Genie can answer questions about past analyses.

## Key decisions

### 1. Pre-train Hex2Vec on 37 cities instead of fitting on the customer's own locations
Fitting the encoder only on the cells around a brand's stores gives a tiny,
biased training set. The embedding then learns "what this brand's
neighbourhoods look like" and nothing else, so similarity scores in a new city
are not comparable. Following the Hex2Vec paper (Woźniak & Szymański, 2021), I
pre-train once on 37 diverse cities and apply the frozen encoder at analysis
time. The cost is a longer one-off training job in the ETL. The benefit is
stable, comparable scores, and a new city can be analysed without retraining.
[`HEX2VEC_EXPLAINER.md`](HEX2VEC_EXPLAINER.md) has the full reasoning.

### 2. Gold tables as a declarative pipeline, not notebooks
The first version had four `CREATE OR REPLACE TABLE` notebooks. Moving them to
SDP materialized views gave me dependency ordering and lineage without any
extra code, and data-quality expectations recorded in the event log. Liquid
clustering is maintained on every refresh, which replaced a separate `OPTIMIZE
... ZORDER` step.
- **Materialized views, not streaming tables.** The source is a Marketplace
  share that's republished per Overture release, not an append-only feed.
  Every refresh can rewrite rows, so streaming tables would be the wrong
  abstraction. The trade-off is a full recompute on each refresh, which is fine
  for a weekly or monthly cadence.
- **Shared silver layer.** `gold_places` (the model's 32 categories) and
  `gold_places_enriched` (all categories, used by Genie and competitor search)
  both read `silver_places`, so the cleaning rules live in one place.
- **Drop rules vs warn rules.** Rows the app can't use (no id, invalid
  coordinates, permanently closed POIs) are dropped. Quality signals that are
  useful to watch but not disqualifying (low confidence, missing address,
  implausible height, city without a polygon) are warn-only, so their counts
  show up in the event log run after run.

### 3. Absorb Overture schema drift in silver
While rebuilding, I found the current Overture release had changed its schema.
`categories.primary` became `taxonomy.primary`, geometry is now native
`GEOMETRY` instead of WKB, and several categories were renamed (`dentist` →
`dental_clinic`/`general_dentistry`, `real_estate` → `real_estate_agent`/…).
The original notebooks would have either failed or silently produced
zero-count features. Silver now maps the new taxonomy back onto the model's
vocabulary, so the trained model and the app's column contracts stay stable.
`supermarket` no longer exists (Overture folded it into `grocery_store`), so
that feature is now always zero. That's a known, documented gap rather than a
silent one.

### 4. City footprints when Overture only has a point
Some major cities have no area polygon in Overture; London, Stockholm and
Reykjavík are just points. Neither the parent division nor the child
divisions help: London's parent is Westminster (about 59 km²), and Greater
London doesn't exist as a division. Instead of the old fixed ±0.15° box, these
cities now get a circle sized from their Overture `population` at 5,000
residents/km², an assumed density in line with large European cores. London
comes out at about 1,770 km² against Greater London's 1,572 km². A
`polygon_source` column records which rule produced each footprint.

### 5. Lakebase for live state, Delta for the analytical record
The app used to keep every analysis in a per-process dict (20 sessions, 1-hour
TTL). A restart, or a second instance, lost all open sessions. The new split:
- **Lakebase (Postgres)** holds what the running app reads and writes in real
  time:
  - sessions, stored as a compact Parquet+JSON payload (deliberately not
    pickle);
  - scored hexagons, indexed by score;
  - the shortlist, which is per-user, mutable state with a status workflow
    and notes that doesn't fit an append-only Delta table.
- **Delta in UC** stays the system of record for Genie, lineage and history.

The project scales to zero, so it costs nothing between demos.

### 6. Cannibalization reported next to the score, not folded into it
Sales transfer from the brand's own nearby stores is the most common reason a
high-similarity site under-delivers. Each candidate gets the distance to its
nearest own store, and the share of its catchment (0.8 km default, a 10-minute walk) that
overlaps that store's catchment, using circle-overlap geometry. I deliberately
didn't fold this into the opportunity score. A real-estate lead may accept
some overlap in a dense, high-performing area, and hiding it inside a single
number would take that judgement away from them.

### 7. What running it end-to-end with captured evidence surfaced
Running the whole build from a fresh deployment and writing the outputs to
[`docs/evidence/`](docs/evidence/) caught four defects that had been invisible
while the code only existed as notebooks:
- **Hex2Vec was training on ~2% of its data.** The training notebook fetched
  results inline (capped at 25 MiB, silently truncated), and pulled POIs and
  buildings with one bounding box spanning every training city from San
  Francisco to Astana. The model saw 4,139 cells and 44k features. It now
  fetches via `EXTERNAL_LINKS` + Arrow, filters to the cities' H3 cells in the
  warehouse, and fails if a result is ever truncated. It now trains on
  **106,365 cells and 5.0M features**.
- **Dependency drift:** `srai` uses a Polars argument removed in Polars 2.0,
  so training and in-app embedding broke on fresh installs. Pinned
  `polars<2`.
- **"Save Analysis" only ever wrote one of five tables.** The staging volume
  was never created, and `poi_count`/`competitor_count` were written as int64
  into `INT` columns. Both are fixed, and the volume grants are now explicit.
- **Genie ranked existing stores as "opportunities".** Its instructions now
  exclude `is_brand_cell` rows and explain the cannibalization columns. Its
  top 10 now matches the app's top 10 for the same analysis.

## How this was built (and where AI helped)

> **TODO (Dilshad):** rewrite this section in your own words. It's the part
> the grader reads most closely for "Build + AI Mindset". Keep it specific:
> which steps you did by hand, which you delegated to an assistant, and where
> you overrode its suggestions.

- **v1 (original accelerator):** built with Cursor. *(Describe your workflow:
  e.g. how you scaffolded the apx app, iterated on the Genie instructions, and
  validated Hex2Vec against the paper.)*
- **v2 (this revision):** I used Claude Code as a pair programmer against the
  live workspace. I set the scope from the FE Bar feedback: Lakeflow, Lakebase,
  evidence, industry framing. The assistant ported the SQL into the pipeline,
  ran it in a scratch pipeline, and surfaced the Overture schema change from
  the first failed run. I chose how to handle it: keep the model vocabulary
  stable, drop closed POIs, use population-scaled footprints over parent
  boundaries. The biggest time saving was the loop of running against real
  data, reading the event log and adjusting. That turned an afternoon of
  trial and error into minutes per iteration.

## What I'd do next
- Log Hex2Vec training to MLflow and register it in UC, with a drift check on
  `gold_places` category counts that triggers retraining when Overture
  releases change the category mix.
- Row filters on the analysis tables so each brand team only sees its own
  history in a shared catalog.
- Turn the per-hexagon `explanation_summary` into a short written
  recommendation grounded in the fingerprint, competitors and cannibalization,
  logged through inference tables.
- Calibrate cannibalization against real sales-transfer data where a customer
  can provide it, instead of the geometric proxy.
