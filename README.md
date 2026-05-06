# Site Selection Accelerator

A Databricks solution accelerator that helps retail and operations teams
identify **whitespace expansion opportunities** for their brand. The app
discovers existing locations, builds a geospatial profile using **Hex2Vec**
embeddings from POI and building data, scores every H3 hexagonal cell in a
target city by neighbourhood similarity, and applies a competition penalty to
surface areas that best match the brand but are not yet saturated.

**Use cases:** franchise expansion, competitive gap analysis, new market entry,
cross-market transfer learning.

---

## Quick Start (5 steps)

> Estimated time: **15–20 minutes** (plus ~15 min for the ETL job to run).

```bash
# 1. Clone and install
git clone https://github.com/Dill2017/site-selection-accelerator.git
cd site-selection-accelerator
uv sync

# 2. Authenticate with your Databricks workspace
databricks auth login --host https://<your-workspace-url>

# 3. Configure — run the interactive setup script
bash setup.sh

# 4. Build and deploy
uv run apx build
databricks bundle deploy

# 5. Run the ETL pipeline (creates tables, Genie Space, model — ~15 min)
databricks bundle run geospatial_etl_job

# 6. Launch the app
databricks bundle run site_selection_app
```

Open the app URL printed in the terminal (or find it in the **Databricks Apps** UI).

If you hit any issues, see [Troubleshooting](#troubleshooting) below.

---

## Prerequisites

Complete **all** of these before running Quick Start step 3.

### 1. Databricks Workspace

| Requirement | Details |
|---|---|
| **Workspace** | Any cloud (AWS, Azure, GCP) with **Unity Catalog** enabled |
| **SQL Warehouse** | Serverless or Pro. The deploying user and the app service principal both need `CAN_USE` permission |
| **Catalog** | You need a catalog you own or have `CREATE SCHEMA` privilege on. If you don't have one, ask your workspace admin to create one for you |

### 2. Install CARTO Overture Maps from the Databricks Marketplace

The ETL pipeline reads geospatial data from three free CARTO datasets. You
**must** install all three before running the ETL job.

**How to install each one:**

1. Open your Databricks workspace
2. Click **Marketplace** in the left sidebar
3. Search for the listing name (see table below)
4. Click **Get** on the listing page
5. Accept the default catalog name (recommended) and click **Get Data**
6. Repeat for all three listings

| # | Search for | Expected Catalog Name | Marketplace Link |
|---|---|---|---|
| 1 | CARTO Overture Maps — Places | `carto_overture_maps_places` | [Open listing](https://marketplace.databricks.com/detail/d268c0c5-a7d6-4267-8149-f6eb6359a7e3/CARTO_Overture-Maps-Places) |
| 2 | CARTO Overture Maps — Divisions | `carto_overture_maps_divisions` | [Open listing](https://marketplace.databricks.com/detail/2ca2de0e-ab6e-4efe-b8a1-3f4e3bfd53d1/CARTO_Overture-Maps-Divisions) |
| 3 | CARTO Overture Maps — Buildings | `carto_overture_maps_buildings` | [Open listing](https://marketplace.databricks.com/detail/14de3db9-b9d2-4f74-8b20-c440b0e2bd40/CARTO_Overture-Maps-Buildings) |

> **If your workspace uses different catalog names** for these datasets (e.g.
> your admin renamed them), `setup.sh` will prompt you for the correct names.
> You can also override the `carto_*_catalog` variables in `databricks.yml`
> manually.

**Verify installation** — run this in a Databricks SQL editor or notebook:

```sql
-- Each query should return rows. If any fails with "catalog not found",
-- that listing hasn't been installed yet.
SELECT COUNT(*) FROM carto_overture_maps_places.carto.overture_places_latest LIMIT 1;
SELECT COUNT(*) FROM carto_overture_maps_divisions.carto.overture_divisions_latest LIMIT 1;
SELECT COUNT(*) FROM carto_overture_maps_buildings.carto.overture_buildings_latest LIMIT 1;
```

### 3. Local Tools

Install these on your local machine:

| Tool | Version | Install |
|---|---|---|
| **Databricks CLI** | v0.239.0+ | [Install guide](https://docs.databricks.com/dev-tools/cli/install.html) |
| **APX CLI** | Latest | `pip install databricks-apx` or [GitHub](https://github.com/databricks-solutions/apx) |
| **Python** | 3.11+ | — |
| **uv** | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` or [docs](https://docs.astral.sh/uv/) |
| **bun** | Latest | `curl -fsSL https://bun.sh/install \| bash` or [bun.sh](https://bun.sh) |

Verify you're authenticated:

```bash
databricks auth env --host https://<your-workspace-url>
# Should print DATABRICKS_HOST and DATABRICKS_TOKEN without errors
```

### 4. Cloud-Specific: Node Type for Hex2Vec Training

The ETL job trains the Hex2Vec model on a single-node cluster. The `setup.sh`
script asks for this, but here's the reference:

| Cloud | `node_type_id` |
|---|---|
| **AWS** | `i3.xlarge` |
| **Azure** | `Standard_DS3_v2` |
| **GCP** | `n1-standard-4` |

---

## Configuration

### Automated (Recommended)

Run the interactive setup script:

```bash
bash setup.sh
```

It asks for your workspace URL, catalog name, schema name, SQL warehouse
display name, node type, and CARTO Marketplace catalog names, then writes
all config files in sync — including the target workspace in `databricks.yml`.

### Manual

If you prefer to edit manually, update **both** of these files — they **must**
match:

**`databricks.yml`** — Bundle variables and target workspace:

```yaml
variables:
  catalog:
    default: "my_catalog"             # Your Unity Catalog catalog
  schema:
    default: "geospatial"             # Schema (created by ETL job)
  warehouse_id:
    lookup:
      warehouse: "My SQL Warehouse"   # Exact display name of your SQL warehouse
  node_type_id:
    default: "i3.xlarge"              # Cloud-specific (see table above)

targets:
  dev:
    workspace:
      host: "https://my-workspace.cloud.databricks.com"  # Your workspace URL
  prod:
    workspace:
      host: "https://my-workspace.cloud.databricks.com"  # Same workspace URL
```

> **Important:** The `workspace.host` in each target tells the Databricks CLI
> where to deploy. Without it, the CLI falls back to your `~/.databrickscfg`
> DEFAULT profile, which may point to a different workspace.

**`packages/app/app.yml`** — App runtime environment:

```yaml
env:
  - name: GOLD_CATALOG
    value: "my_catalog"               # Must match catalog above
  - name: GOLD_SCHEMA
    value: "geospatial"               # Must match schema above
```

> **Important:** If `GOLD_CATALOG` / `GOLD_SCHEMA` in `app.yml` don't match
> the `catalog` / `schema` variables in `databricks.yml`, the app will fail at
> runtime with "table not found" errors.

### Optional: CARTO Catalog Overrides

The `setup.sh` script handles this interactively, but if you need to override
manually after setup:

```yaml
# In databricks.yml under variables:
  carto_divisions_catalog:
    default: "my_custom_carto_divisions"
  carto_places_catalog:
    default: "my_custom_carto_places"
  carto_buildings_catalog:
    default: "my_custom_carto_buildings"
```

---

## Deploy Step by Step

### Step 1: Clone and install dependencies

```bash
git clone https://github.com/Dill2017/site-selection-accelerator.git
cd site-selection-accelerator
uv sync
```

### Step 2: Authenticate with Databricks

```bash
databricks auth login --host https://<your-workspace-url>
```

Follow the browser-based OAuth flow. Verify with:

```bash
databricks warehouses list
# Should list your SQL warehouses — note the display name of the one you want to use
```

### Step 3: Configure

```bash
bash setup.sh
```

Or edit `databricks.yml` and `packages/app/app.yml` manually (see
[Configuration](#configuration)).

### Step 4: Build and deploy

```bash
uv run apx build
databricks bundle deploy
```

> **Note:** `apx build` downloads build dependencies from PyPI. If your
> environment blocks PyPI, see [Build in Restricted Environments](#build-in-restricted-environments).

### Step 5: Run the ETL pipeline

This creates the schema, gold tables, analysis tables, Genie Space, and
pretrained Hex2Vec model — everything the app needs:

```bash
databricks bundle run geospatial_etl_job
```

The command prints a URL to the job run. You can monitor progress there.

**What it does (in order):**

| Task | Duration | Description |
|---|---|---|
| `setup_schema` | ~5s | Creates `{catalog}.{schema}` if it doesn't exist |
| `create_gold_cities` | ~1 min | Builds city polygon lookup from CARTO Divisions |
| `create_gold_places` | ~2 min | Extracts POI coordinates and categories from CARTO Places |
| `create_gold_buildings` | ~3 min | Extracts building footprints from CARTO Buildings |
| `create_gold_places_enriched` | ~2 min | Full POI table with brands, addresses, coordinates |
| `create_analysis_tables` | ~5s | DDL for the five analysis result tables |
| `create_gold_radiance` | ~2 min | *(Optional)* Computes mean VIIRS radiance per H3 cell. Skips if VIIRS file not uploaded |
| `setup_genie_space` | ~30s | Creates Genie Space, grants app service principal access, writes config |
| `train_hex2vec` | ~5 min | Trains Hex2Vec embedding model on 37 cities |

### Step 6: Launch the app

```bash
databricks bundle run site_selection_app
```

Open the app URL from the **Databricks Apps** UI. On first load you should see:
- Country dropdown populated with country codes
- City dropdown populated after selecting a country
- All POI categories checked by default

---

## Permissions

### What's Handled Automatically

The bundle deployment and ETL job handle most permissions for you:

| Permission | How It's Granted |
|---|---|
| App SP gets `CAN_USE` on SQL Warehouse | Bundle resource binding in `resources/site_selection_app.yml` |
| App SP gets `CAN_RUN` on Genie Space | `setup_genie_space.py` ETL task |
| App SP gets `USE CATALOG` on your catalog | `setup_genie_space.py` ETL task |
| App SP gets `USE SCHEMA`, `SELECT`, `MODIFY` on your schema | `setup_genie_space.py` ETL task |
| App SP gets `CAN_MANAGE_RUN` on radiance job | Bundle resource binding |

### What You Need (Deploying User)

The user running `databricks bundle deploy` and `databricks bundle run` needs:

| Resource | Permission |
|---|---|
| Workspace | Ability to create apps and jobs |
| Target catalog | `USE CATALOG`, `CREATE SCHEMA` |
| CARTO catalogs (all three) | `USE CATALOG`, `USE SCHEMA`, `SELECT` |

> **CARTO catalog permissions:** After installing from Marketplace, the data
> is typically readable by all workspace users. If you get "permission denied"
> errors on CARTO tables, ask your workspace admin to grant `USE CATALOG` and
> `SELECT` on the CARTO catalogs.

### Manual Permission Grants (If Automatic Grants Fail)

If the ETL job's `setup_genie_space` task fails to grant permissions (e.g. due
to workspace restrictions), grant them manually. Find the app service principal
name in **Databricks UI → Apps → site-selection-accelerator → Settings**, then:

```sql
-- Replace <sp_name> with the app's service principal display name
-- Replace <catalog>.<schema> with your values
GRANT USE CATALOG ON CATALOG `<catalog>` TO `<sp_name>`;
GRANT USE SCHEMA ON SCHEMA `<catalog>`.`<schema>` TO `<sp_name>`;
GRANT SELECT ON SCHEMA `<catalog>`.`<schema>` TO `<sp_name>`;
GRANT MODIFY ON SCHEMA `<catalog>`.`<schema>` TO `<sp_name>`;
```

For the SQL warehouse (run in terminal):

```bash
# Find the warehouse ID
databricks warehouses list

# Grant CAN_USE
databricks warehouses set-permissions <warehouse_id> \
  --json '{"access_control_list": [{"service_principal_name": "<sp_client_id>", "permission_level": "CAN_USE"}]}'
```

---

## What You Get

| Asset | Description |
|---|---|
| **Databricks App** | Interactive full-stack app (React + FastAPI) for running brand site analysis |
| **ETL Pipeline** | DABs job that builds gold tables from CARTO Overture Maps and trains the Hex2Vec model |
| **Gold Tables** | `gold_cities`, `gold_places`, `gold_buildings`, `gold_places_enriched`, `gold_radiance` (optional) in Unity Catalog |
| **Analysis Tables** | `analyses`, `analysis_hexagons`, `analysis_brand_profiles`, `analysis_fingerprints`, `analysis_competitors` — every analysis run persisted to Delta |
| **Hex2Vec Model** | Multi-city pretrained geospatial embedding model stored in a UC Volume |
| **Genie Space** | Natural-language SQL exploration over both the base data and your analysis results |

---

## Using the App

### Running an Analysis

1. **Select a target market** — choose country and city from the dropdowns.
2. **Choose your brand** — enter a brand name, lat/lon coordinates, street
   addresses, or draw locations on the map.
   - **Brand mode** — enter a brand name; Genie finds all matching locations.
   - **Address mode** — enter addresses; the app geocodes them and shows a POI
     checklist for disambiguation when multiple POIs share an address.
   - **Coordinate mode** — paste lat/lon pairs directly.
   - **Map drawing** — drop points or draw polygons on the map.
3. **Tune parameters** — adjust H3 resolution, POI categories, building
   features, and competition sensitivity (beta).
4. **Click "Find Opportunities"** — the pipeline runs with live progress,
   then the map fills with scored hexagons.
5. **Explore** — hover hexagons for quick stats, click any hexagon for a
   detailed fingerprint with LLM-generated insight, view the brand profile.

### Saving Results to Delta

Click **Save Analysis** in the sidebar after an analysis completes. This
persists all outputs to five Delta tables, each keyed by a unique
`analysis_id`:

| Table | Contents |
|---|---|
| `analyses` | Registry of every run — brand, city, parameters, timestamp |
| `analysis_hexagons` | Every scored H3 cell with similarity, opportunity score, POI/competitor counts |
| `analysis_brand_profiles` | Average category distribution across brand locations |
| `analysis_fingerprints` | Per-hexagon category comparison with LLM insight (top 20 cells) |
| `analysis_competitors` | Competitor POIs found in high-similarity cells |

The Genie Space includes these tables, so you can ask questions like
*"Show me the top 10 hexagons by similarity for Starbucks in London"* in
natural language.

### Accessing All Assets

Click the **Assets** button (bottom-right corner) to open a dialog with direct
links to:

- Databricks Workspace
- Genie Space (Brand & Competition Explorer)
- Hex2Vec pretrained model (UC Volume)
- All gold and analysis Delta tables
- Recently saved analyses

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        Databricks App (apx)                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  React + TypeScript Frontend (deck.gl, MapLibre, shadcn/ui)       │   │
│  │                                                                    │   │
│  │  OpportunityMap ─ ConfigSidebar ─ BrandProfileDialog               │   │
│  │  FingerprintPanel ─ AssetsPopover                                  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                               │ /api/*                                    │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Backend                                                   │   │
│  │                                                                    │   │
│  │  POST /analyze             ─ SSE pipeline (tessellate, embed, score)│   │
│  │  POST /resolve-addresses  ─ geocode + POI lookup for disambiguation│   │
│  │  GET  /results/{id}       ─ cached analysis for map rendering      │   │
│  │  POST /results/{id}/persist ─ save analysis to Delta tables        │   │
│  │  GET  /assets             ─ links to all workspace assets          │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                               │                                           │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  Python Modules                                                    │   │
│  │  pipeline ─ embeddings ─ similarity ─ brand_search                 │   │
│  │  explainability ─ persist ─ config ─ db                            │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
                               │
          ┌────────────────────┼─────────────────────┐
          ▼                    ▼                      ▼
  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐
  │ Unity Catalog   │  │ Genie Space     │  │ SQL Warehouse    │
  │                 │  │                 │  │                  │
  │ Gold tables     │  │ NL → SQL over   │  │ H3 functions     │
  │ Analysis tables │  │ gold + analysis │  │ ai_query() LLM   │
  │ Hex2Vec model   │  │ tables          │  │                  │
  └────────────────┘  └─────────────────┘  └──────────────────┘
          ▲
  ┌────────────────┐
  │ ETL Job (DABs) │
  │                │
  │ CARTO Overture │
  │ → gold tables  │
  │ → analysis DDL │
  │ → Genie Space  │
  │ → Hex2Vec      │
  └────────────────┘
```

---

## Project Structure

```
site-selection-accelerator/
├── databricks.yml                        # Bundle config — catalog, schema, warehouse
├── setup.sh                             # Interactive configuration script
├── pyproject.toml                        # Root uv workspace
├── resources/
│   ├── site_selection_app.yml            # Databricks App resource
│   ├── geospatial_etl_job.yml           # ETL job (SQL + Python tasks)
│   └── radiance_on_demand_job.yml       # On-demand radiance job
├── packages/app/                         # Full-stack application (apx)
│   ├── app.yml                           # App runtime config (env vars)
│   ├── pyproject.toml                    # Python dependencies
│   ├── package.json                      # Frontend dependencies
│   └── src/site_selection/
│       ├── backend/
│       │   ├── app.py                    # FastAPI entry point
│       │   ├── router.py                 # API routes
│       │   ├── models.py                 # Pydantic models
│       │   └── cache.py                  # In-memory session cache
│       └── ui/
│           ├── routes/index.tsx          # Main page
│           ├── components/
│           │   ├── map/                  # deck.gl map layers
│           │   ├── sidebar/              # Config panel with Save Analysis
│           │   ├── brand-profile/        # Brand profile dialog
│           │   ├── fingerprint/          # Hexagon detail panel
│           │   └── assets/               # Assets dialog
│           └── lib/
│               ├── types.ts              # TypeScript interfaces
│               └── use-analyze.ts        # SSE analysis hook
└── src/
    ├── app/                              # Python modules
    │   ├── config.py                     # Table refs, categories, constants
    │   ├── db.py                         # DBSQL execution via SDK
    │   ├── pipeline.py                   # Geospatial queries
    │   ├── radiance.py                   # VIIRS nighttime radiance processing
    │   ├── embeddings.py                 # SRAI Hex2Vec pipeline
    │   ├── similarity.py                 # Cosine similarity + opportunity scoring
    │   ├── brand_search.py               # Genie brand discovery + competition
    │   ├── explainability.py             # Score explanations + LLM insights
    │   └── persist.py                    # Delta table persistence
    └── pipeline/
        ├── setup_genie_space.py          # Genie Space provisioning
        ├── train_hex2vec.py              # Multi-city Hex2Vec training
        └── transformations/
            ├── setup_schema.sql
            ├── gold_cities.sql
            ├── gold_places.sql
            ├── gold_buildings.sql
            ├── gold_places_enriched.sql
            ├── create_gold_radiance.py   # VIIRS radiance ETL (optional)
            └── analysis_tables.sql       # Analysis result DDL
```

---

## How It Works

### ETL Pipeline (one-time setup)

The `geospatial_etl_job` runs these tasks in order:

1. **Create schema** — `CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}`
2. **Gold tables** — transform CARTO Overture Maps into optimised lookup tables
   (`gold_cities`, `gold_places`, `gold_buildings`, `gold_places_enriched`)
3. **Analysis tables** — create the five analysis result tables
4. **Genie Space** — provision a Genie Space with H3 spatial instructions,
   analysis table instructions, and example queries; grant the app service
   principal `CAN_RUN` access and `SELECT`/`MODIFY` on the schema
5. **Hex2Vec training** — train an embedding model on 37 cities and save to a
   UC Volume

### Analysis Pipeline (per run)

1. **Brand resolution** — discover locations via Genie (brand name), geocoding
   with POI disambiguation (addresses), or direct input (coordinates / map
   drawing). Source locations can be outside the target city/country for
   cross-market analysis.
2. **Tessellation** — fill the target city polygon with H3 cells
3. **Feature assembly** — query POIs and buildings, merge into a unified feature
   table
4. **Hex2Vec embeddings** — transform features using the pretrained model (or
   train from scratch as fallback)
5. **Similarity scoring** — cosine similarity between brand profile and every
   city cell
6. **Opportunity scoring** — combines similarity and competition into a
   single score using `similarity * (1 - beta * competition_score)`,
   normalised by percentile rank.
7. **Persist (optional)** — save all results to Delta when the user clicks
   Save Analysis

---

## Troubleshooting

### Setup & Configuration Errors

| Symptom | Cause | Fix |
|---|---|---|
| `setup.sh` fails with "python3 not found" | Python 3 not on PATH | Install Python 3.11+ and ensure `python3` is in your PATH |
| `databricks auth login` fails | CLI not installed or wrong version | Install Databricks CLI v0.239.0+ from [docs](https://docs.databricks.com/dev-tools/cli/install.html) |
| `uv sync` fails | `uv` not installed | Install with `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### Deployment Errors

| Symptom | Cause | Fix |
|---|---|---|
| `apx build` fails with "connection refused" or PyPI timeout | PyPI access blocked | See [Build in Restricted Environments](#build-in-restricted-environments) |
| `bundle deploy` goes to the wrong workspace | `workspace.host` not set in targets | Run `bash setup.sh` or set `workspace.host` under each target in `databricks.yml` |
| `bundle deploy` fails with "does not have permissions on job" | Stale Terraform state from a previous workspace | Delete `.databricks/bundle/` and redeploy: `rm -rf .databricks/bundle/ && databricks bundle deploy`. Running `bash setup.sh` again will also detect and clean this automatically |
| `bundle deploy` fails with "Node type X is not supported" | Node type doesn't match the cloud (e.g. Azure type on AWS) | Run `bash setup.sh` — it auto-detects the cloud from your workspace URL and sets the right default. Or edit `node_type_id` in `databricks.yml` manually (AWS: `i3.xlarge`, Azure: `Standard_DS3_v2`, GCP: `n1-standard-4`) |
| `bundle deploy` fails with "warehouse not found" | Warehouse display name doesn't match | Run `databricks warehouses list` and use the **exact** display name in `databricks.yml` |
| `bundle deploy` fails with "catalog CHANGE_ME" | Forgot to configure | Run `bash setup.sh` or edit `databricks.yml` manually |
| `bundle deploy` fails with empty `node_type_id` | Variable not set for your cloud | Set the correct instance type (see [Prerequisites](#4-cloud-specific-node-type-for-hex2vec-training)) |

### ETL Job Errors

| Symptom | Cause | Fix |
|---|---|---|
| SQL tasks fail with "catalog not found" | CARTO catalogs not installed | Install all three from Marketplace (see [Prerequisites](#2-install-carto-overture-maps-from-the-databricks-marketplace)) |
| SQL tasks fail with "permission denied" on CARTO tables | User lacks `SELECT` on CARTO catalogs | Ask workspace admin to grant `USE CATALOG` + `SELECT` on the CARTO catalogs |
| `train_hex2vec` fails to provision cluster | Wrong `node_type_id` for your cloud | Update `databricks.yml` with the correct instance type |
| `setup_genie_space` fails with permission error | Insufficient privileges on target catalog | Ensure deploying user has `USE CATALOG`, `CREATE SCHEMA` |

### App Runtime Errors

| Symptom | Cause | Fix |
|---|---|---|
| Empty country/city dropdowns | Gold tables don't exist | Run `databricks bundle run geospatial_etl_job` |
| `Countries API: 500` | App can't connect to SQL warehouse | Check that `DATABRICKS_WAREHOUSE_ID` is set in `app.yml` via the `sql-warehouse` resource binding |
| `500 — You do not have permission to use the SQL Warehouse` | App service principal lacks `CAN_USE` | Grant manually — see [Manual Permission Grants](#manual-permission-grants-if-automatic-grants-fail) |
| `500 — GOLD_CATALOG is not configured` | `GOLD_CATALOG` still set to `CHANGE_ME` | Run `bash setup.sh` or edit `packages/app/app.yml`, then redeploy |
| `500 — Table not found` | Catalog/schema mismatch between config files | Ensure `GOLD_CATALOG`/`GOLD_SCHEMA` in `app.yml` match bundle variables in `databricks.yml` |
| Save Analysis fails | App SP can't modify tables | Grant `MODIFY` on the schema to the app SP (see [Manual Permission Grants](#manual-permission-grants-if-automatic-grants-fail)) |
| "No POIs found" | No data for selected categories in that city | Broaden category selection or use a coarser H3 resolution |
| Fingerprint shows generic text instead of LLM insight | Workspace doesn't have Foundation Model access | Non-critical — the app works without it. Enable pay-per-token Foundation Models in your workspace for LLM-powered insights |

---

## Optional Features

### VIIRS Nighttime Lights (Economic Activity Proxy)

The app can optionally display **VIIRS nighttime radiance** per H3 cell as
a proxy for economic activity. If the data is present, radiance values appear
in the hex tooltip; if absent, everything still works without it.

The VIIRS annual composite is published by the
[Earth Observation Group (EOG)](https://eogdata.mines.edu/products/vnl/#annual_v2)
under **CC BY 4.0** license.

**Steps to enable:**

1. Create a free account at https://eogdata.mines.edu
2. Download the **Annual VNL V2** `median_masked` GeoTIFF from the EOG website
   (browser download — the file is ~2-3 GB)
3. Unzip the `.tif.gz` to get the `.tif` file
4. Create the Volume (if it doesn't exist):
   ```sql
   CREATE VOLUME IF NOT EXISTS <catalog>.<schema>.viirs_nighttime_lights;
   ```
5. Upload the `.tif` file to the Volume via the Databricks UI (drag-and-drop)
   or CLI:
   ```bash
   databricks fs cp ./viirs_file.tif dbfs:/Volumes/<catalog>/<schema>/viirs_nighttime_lights/
   ```
6. Re-run the ETL job — the `create_gold_radiance` task picks up the file
   automatically and precomputes radiance for the 37 training cities

> **Citation (required by CC BY 4.0):**
> Elvidge, C.D, Zhizhin, M., Ghosh T., Hsu FC, Taneja J. "Annual time
> series of global VIIRS nighttime lights derived from monthly averages:
> 2012 to 2019". Remote Sensing 2021, 13(5), p.922

### LLM-Powered Insights

The app uses two Foundation Model endpoints for optional AI features:

| Feature | Endpoint | Fallback |
|---|---|---|
| Hexagon fingerprint insights | `databricks-meta-llama-3-3-70b-instruct` via `ai_query()` | Rule-based text summary |
| Competition category filtering | `databricks-claude-opus-4-6` via Model Serving | Frequency-based top categories |

These are **pay-per-token** endpoints available on most Databricks workspaces.
If they're not available or fail, the app gracefully falls back to non-LLM
alternatives. No action required — everything works without them.

---

## Local Development

```bash
uv sync
uv run apx bun install

# Create packages/app/.env with your local settings:
cat > packages/app/.env << 'EOF'
DATABRICKS_CONFIG_PROFILE=DEFAULT
GOLD_CATALOG=my_catalog
GOLD_SCHEMA=geospatial
DATABRICKS_WAREHOUSE_ID=<your-warehouse-id>
EOF

uv run apx dev start    # backend + frontend + OpenAPI watcher
uv run apx dev status   # check health
uv run apx dev logs     # view logs
uv run apx dev check    # type checks (TypeScript + Python)
uv run apx dev stop     # stop servers
```

Find your warehouse ID with:

```bash
databricks warehouses list --output json | python3 -c "
import json, sys
for w in json.load(sys.stdin):
    print(f\"{w['id']}  {w['name']}\")
"
```

---

## Configuration Reference

| File | Setting | Purpose |
|---|---|---|
| `databricks.yml` | `targets.*.workspace.host` | Databricks workspace URL for deployment |
| `databricks.yml` | `variables.catalog` | Unity Catalog catalog for all tables |
| `databricks.yml` | `variables.schema` | Schema for all tables (default: `geospatial`) |
| `databricks.yml` | `variables.warehouse_id` | SQL warehouse (looked up by display name) |
| `databricks.yml` | `variables.node_type_id` | Cloud-specific instance type for Hex2Vec training |
| `databricks.yml` | `variables.carto_*_catalog` | Override CARTO Marketplace catalog names |
| `packages/app/app.yml` | `GOLD_CATALOG` env | Must match `variables.catalog` |
| `packages/app/app.yml` | `GOLD_SCHEMA` env | Must match `variables.schema` |
| `packages/app/app.yml` | `GENIE_SPACE_ID` env | Leave empty — auto-created by ETL |

---

## Build in Restricted Environments

The `apx build` command uses `hatchling` and `uv-dynamic-versioning` as Python
build-system dependencies, which are fetched from PyPI at build time.

If your environment **blocks PyPI access** (corporate firewall, air-gapped
network), the build will fail with a connection error. Options:

1. **Pre-install build deps** — run `uv pip install hatchling uv-dynamic-versioning`
   before building, then set `UV_NO_BUILD_ISOLATION=1`:
   ```bash
   UV_NO_BUILD_ISOLATION=1 uv run apx build
   ```

2. **Use a PyPI mirror** — set `UV_INDEX_URL` to your internal mirror:
   ```bash
   UV_INDEX_URL=https://pypi.internal.example.com/simple uv run apx build
   ```

3. **Build on a machine with internet** — run `uv run apx build` on a connected
   machine, then copy `packages/app/.build/` to the restricted environment
   before running `databricks bundle deploy`.

---

## Extending the Accelerator

- **Add POI categories** — edit `CATEGORY_GROUPS` in `src/app/config.py` and
  the `WHERE` clause in `gold_places.sql`, then re-run the ETL.
- **Add building categories** — edit `BUILDING_CATEGORY_GROUPS` in `config.py`
  and the logic in `gold_buildings.sql`.
- **Retrain Hex2Vec** — edit `HEX2VEC_TRAINING_CITIES` in `config.py`, then
  re-run the ETL. The app picks up the new model on next restart.
- **Custom Genie instructions** — edit `src/pipeline/setup_genie_space.py`.
- **Refresh data** — run `databricks bundle run geospatial_etl_job` whenever
  the upstream CARTO data updates.

---

## Cleanup

To remove all deployed resources from your workspace:

```bash
databricks bundle destroy
```

This removes the app, jobs, and other bundle-managed resources. The catalog,
schema, and tables are **not** deleted — remove them manually if needed:

```sql
DROP SCHEMA IF EXISTS `<catalog>`.`<schema>` CASCADE;
```

---

## Third-Party Licenses & Acknowledgements

This accelerator builds on open-source software and publicly licensed datasets.
All dependencies are distributed under permissive licenses (Apache-2.0, MIT,
BSD-3-Clause, ISC) or open data licenses (CC BY 4.0). No dependencies are
redistributed in this repository — they are installed at build time from PyPI,
npm, or the Databricks Marketplace.

### Python Dependencies

Declared in `packages/app/pyproject.toml`.

| Package | License | Source |
|---|---|---|
| fastapi | MIT | https://github.com/fastapi/fastapi |
| pydantic-settings | MIT | https://github.com/pydantic/pydantic-settings |
| uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| databricks-sdk | Apache-2.0 | https://github.com/databricks/databricks-sdk-py |
| pandas | BSD-3-Clause | https://github.com/pandas-dev/pandas |
| numpy | BSD-3-Clause | https://github.com/numpy/numpy |
| h3 | Apache-2.0 | https://github.com/uber/h3-py |
| scikit-learn | BSD-3-Clause | https://github.com/scikit-learn/scikit-learn |
| geopandas | BSD-3-Clause | https://github.com/geopandas/geopandas |
| shapely | BSD-3-Clause | https://github.com/shapely/shapely |
| srai | Apache-2.0 | https://github.com/kraina-ai/srai |
| geopy | MIT | https://github.com/geopy/geopy |
| pyarrow | Apache-2.0 | https://github.com/apache/arrow |
| python-dotenv | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| rasterio | BSD-3-Clause | https://github.com/rasterio/rasterio |
| h3ronpy | MIT / Apache-2.0 | https://github.com/nmandery/h3ronpy |
| hatchling (build) | MIT | https://github.com/pypa/hatch |
| uv-dynamic-versioning (build) | MIT | https://github.com/ninoseki/uv-dynamic-versioning |

### Frontend (Node.js / npm) Dependencies

Declared in `packages/app/package.json`.

| Package | License | Source |
|---|---|---|
| react, react-dom | MIT | https://github.com/facebook/react |
| @deck.gl/* (deck.gl) | MIT | https://github.com/visgl/deck.gl |
| maplibre-gl | BSD-3-Clause | https://github.com/maplibre/maplibre-gl-js |
| react-map-gl | MIT | https://github.com/visgl/react-map-gl |
| @radix-ui/react-* | MIT | https://github.com/radix-ui/primitives |
| shadcn/ui (component patterns) | MIT | https://github.com/shadcn-ui/ui |
| @tanstack/react-query | MIT | https://github.com/TanStack/query |
| @tanstack/react-router | MIT | https://github.com/TanStack/router |
| recharts | MIT | https://github.com/recharts/recharts |
| terra-draw, terra-draw-maplibre-gl-adapter | MIT | https://github.com/JamesLMilner/terra-draw |
| tailwindcss, @tailwindcss/vite | MIT | https://github.com/tailwindlabs/tailwindcss |
| tw-animate-css | MIT | https://github.com/Wombosvideo/tw-animate-css |
| axios | MIT | https://github.com/axios/axios |
| lucide-react | ISC | https://github.com/lucide-icons/lucide |
| motion | MIT | https://github.com/motiondivision/motion |
| sonner | MIT | https://github.com/emilkowalski/sonner |
| class-variance-authority | Apache-2.0 | https://github.com/joe-bell/cva |
| clsx | MIT | https://github.com/lukeed/clsx |
| tailwind-merge | MIT | https://github.com/dcastil/tailwind-merge |
| react-error-boundary | MIT | https://github.com/bvaughn/react-error-boundary |
| react-is | MIT | https://github.com/facebook/react |
| @opentelemetry/* | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-js |
| typescript | Apache-2.0 | https://github.com/microsoft/TypeScript |
| vite, @vitejs/plugin-react | MIT | https://github.com/vitejs/vite |
| smol-toml | MIT | https://github.com/squirrelchat/smol-toml |

### Data Sources

| Source | License | How It's Used |
|---|---|---|
| CARTO Overture Maps — Places, Divisions, Buildings | CC BY 4.0 | Installed by the user from the Databricks Marketplace. Not redistributed. |
| VIIRS Annual Nighttime Lights V2 (Earth Observation Group, Colorado School of Mines) | CC BY 4.0 | Optional. Downloaded by the user from https://eogdata.mines.edu. Not redistributed. Citation in the [VIIRS Nighttime Lights](#viirs-nighttime-lights-economic-activity-proxy) section. |

### Databricks-Managed Services

The app calls the following Databricks-managed Foundation Model endpoints when
available. These are not redistributed and are governed by the Databricks
service terms in your workspace:

- `databricks-meta-llama-3-3-70b-instruct` (via `ai_query()`)
- `databricks-claude-opus-4-6` (via Model Serving)

Both are optional — the app falls back to non-LLM alternatives if they are
unavailable.

---

## License

This solution accelerator is provided as-is for demonstration purposes.
