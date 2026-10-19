"""Capture execution evidence for a deployed Site Selection Accelerator.

Run after `databricks bundle deploy` + `databricks bundle run geospatial_etl_job`
and with the app running. Everything written to docs/evidence/ is read back
from the workspace — job run state, the Lakeflow event log, table contents,
Genie answers, live app API responses and Lakebase rows — so the folder is a
reproducible record that the build ran end to end, not a description of it.

    uv run --project packages/app python scripts/capture_evidence.py \
        --profile <profile> --catalog <catalog> --schema <schema> \
        --brand "Pret A Manger" --country GB --city London

Sections can be re-run individually with --only (e.g. --only genie app).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "evidence"

ETL_JOB_SUFFIX = "Site Selection - Refresh Geospatial Data"
PIPELINE_SUFFIX = "Site Selection - Overture Medallion Pipeline"
APP_NAME = "site-selection-accelerator"


# -- helpers -------------------------------------------------------------------

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ms_to_iso(ms: int | None) -> str:
    if not ms:
        return "—"
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def dur(ms: int | None) -> str:
    if not ms:
        return "—"
    s = int(ms / 1000)
    return f"{s // 60}m {s % 60:02d}s"


def md_table(rows: list[dict], cols: list[str] | None = None) -> str:
    if not rows:
        return "_(no rows)_\n"
    cols = cols or list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_cell(r.get(c)) for c in cols) + " |")
    return "\n".join(out) + "\n"


def _cell(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    if isinstance(v, int):
        return f"{v:,}"
    return str(v).replace("|", "\\|").replace("\n", " ")


def write(name: str, title: str, body: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(f"# {title}\n\n_Captured {now()} by `scripts/capture_evidence.py`._\n\n{body}")
    print(f"wrote {path.relative_to(REPO)}")


class Sql:
    def __init__(self, w: WorkspaceClient, warehouse_id: str):
        self.w, self.wh = w, warehouse_id

    def rows(self, sql: str) -> list[dict]:
        r = self.w.statement_execution.execute_statement(
            warehouse_id=self.wh, statement=sql, wait_timeout="50s",
        )
        while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(2)
            r = self.w.statement_execution.get_statement(r.statement_id)
        if r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"{r.status.error.message if r.status.error else r.status.state}\n{sql}")
        cols = [c.name for c in r.manifest.schema.columns]
        types = [c.type_name.value if c.type_name else "STRING" for c in r.manifest.schema.columns]
        out = []
        for raw in (r.result.data_array or []) if r.result else []:
            out.append({c: _coerce(v, t) for c, v, t in zip(cols, raw, types)})
        return out


def _coerce(v, t):
    if v is None:
        return None
    if t in ("LONG", "INT", "SHORT", "BYTE"):
        return int(v)
    if t in ("DOUBLE", "FLOAT", "DECIMAL"):
        return float(v)
    if t == "BOOLEAN":
        return v == "true"
    return v


def find_job(w: WorkspaceClient, suffix: str):
    for j in w.jobs.list(name=None):
        if j.settings and j.settings.name and j.settings.name.endswith(suffix):
            return j
    raise LookupError(f"No job named *{suffix}")


def find_pipeline(w: WorkspaceClient, suffix: str):
    for p in w.pipelines.list_pipelines():
        if p.name and p.name.endswith(suffix):
            return p
    raise LookupError(f"No pipeline named *{suffix}")


# -- sections ------------------------------------------------------------------

def section_job(w: WorkspaceClient, ctx: dict) -> None:
    job = find_job(w, ETL_JOB_SUFFIX)
    runs = list(w.jobs.list_runs(job_id=job.job_id, limit=5, expand_tasks=True))
    done = [r for r in runs if r.state and r.state.result_state is not None]
    if not done:
        raise RuntimeError("ETL job has no finished runs yet")
    run = w.jobs.get_run(done[0].run_id)
    tasks = []
    for t in sorted(run.tasks or [], key=lambda t: t.start_time or 0):
        kind = "pipeline" if t.pipeline_task else "notebook" if t.notebook_task else "?"
        tasks.append({
            "task": t.task_key,
            "type": kind,
            "result": t.state.result_state.value if t.state and t.state.result_state else "—",
            "start": ms_to_iso(t.start_time),
            "duration": dur((t.end_time or 0) - (t.start_time or 0)) if t.end_time else "—",
        })
    body = (
        f"- **Job:** `{job.settings.name}` (job_id `{job.job_id}`)\n"
        f"- **Run:** `{run.run_id}` — [{run.run_page_url}]({run.run_page_url})\n"
        f"- **Result:** **{run.state.result_state.value}**\n"
        f"- **Started:** {ms_to_iso(run.start_time)} · **Wall time:** "
        f"{dur((run.end_time or 0) - (run.start_time or 0))}\n\n"
        "## Tasks\n\n" + md_table(tasks)
    )
    write("01_etl_job_run.md", "ETL job run (Lakeflow Jobs)", body)


def section_pipeline(w: WorkspaceClient, sql: Sql, ctx: dict) -> None:
    p = find_pipeline(w, PIPELINE_SUFFIX)
    pid = p.pipeline_id
    upd = sql.rows(
        f"""SELECT origin.update_id AS update_id, MIN(timestamp) AS started, MAX(timestamp) AS ended
            FROM event_log('{pid}') WHERE event_type = 'update_progress'
              AND details:update_progress:state = 'COMPLETED'
            GROUP BY 1 ORDER BY ended DESC LIMIT 1"""
    )
    if not upd:
        raise RuntimeError("Pipeline has no completed update yet")
    uid = upd[0]["update_id"]
    flows = sql.rows(
        f"""SELECT split(origin.flow_name, '\\\\.')[2] AS dataset,
                   MAX(details:flow_progress:metrics:num_output_rows)::BIGINT AS output_rows,
                   MAX(details:flow_progress:data_quality:dropped_records)::BIGINT AS dropped_rows
            FROM event_log('{pid}')
            WHERE event_type = 'flow_progress' AND origin.update_id = '{uid}'
              AND details:flow_progress:status = 'COMPLETED'
            GROUP BY 1 ORDER BY 1"""
    )
    exp = sql.rows(
        f"""SELECT split(origin.flow_name, '\\\\.')[2] AS dataset, e.name AS expectation,
                   SUM(e.passed_records) AS passed, SUM(e.failed_records) AS failed
            FROM event_log('{pid}')
            LATERAL VIEW explode(from_json(details:flow_progress:data_quality:expectations,
                'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x AS e
            WHERE event_type = 'flow_progress' AND origin.update_id = '{uid}'
            GROUP BY ALL ORDER BY 1, 2"""
    )
    for r in exp:
        total = (r["passed"] or 0) + (r["failed"] or 0)
        r["failed_pct"] = f"{100 * (r['failed'] or 0) / total:.2f}%" if total else "—"
    body = (
        f"- **Pipeline:** `{p.name}` (`{pid}`), serverless, triggered by the ETL job\n"
        f"- **Update:** `{uid}` · {upd[0]['started']} → {upd[0]['ended']}\n\n"
        "Bronze is the CARTO Overture Marketplace share (read zero-copy over Delta Sharing); "
        "silver and gold are materialized views defined in `src/pipeline/lakeflow/`.\n\n"
        "## Datasets refreshed\n\n" + md_table(flows) +
        "\n## Data-quality expectations\n\n"
        "`DROP ROW` expectations remove the row; the others are warn-only and are tracked so "
        "drift in Overture's data shows up in the event log.\n\n" + md_table(exp)
    )
    write("02_pipeline_data_quality.md", "Lakeflow Declarative Pipeline — run and data quality", body)


def section_tables(w: WorkspaceClient, sql: Sql, ctx: dict) -> None:
    fq = f"`{ctx['catalog']}`.`{ctx['schema']}`"
    names = ["silver_places", "silver_buildings", "gold_places", "gold_places_enriched",
             "gold_buildings", "gold_cities"]
    union = " UNION ALL ".join(f"SELECT '{n}' AS table_name, COUNT(*) AS row_count FROM {fq}.{n}" for n in names)
    counts = sql.rows(union)
    sources = sql.rows(
        f"SELECT polygon_source, COUNT(*) AS cities FROM {fq}.gold_cities GROUP BY 1 ORDER BY 2 DESC"
    )
    sample = sql.rows(
        f"""SELECT country, city_name, population, polygon_source, has_polygon,
                   ROUND(center_lat, 4) AS center_lat, ROUND(center_lon, 4) AS center_lon
            FROM {fq}.gold_cities
            WHERE (country, city_name) IN (('GB','London'), ('FR','Paris'), ('US','New York'),
                                           ('DE','Berlin'), ('SE','Stockholm'))
            ORDER BY population DESC"""
    )
    cats = sql.rows(
        f"SELECT category, COUNT(*) AS pois FROM {fq}.gold_places GROUP BY 1 ORDER BY 2 DESC LIMIT 12"
    )
    body = (
        "## Row counts\n\n" + md_table(counts) +
        "\n## How each city footprint was resolved (`gold_cities.polygon_source`)\n\n" + md_table(sources) +
        "\n## Sample cities\n\n" + md_table(sample) +
        "\n## Top model categories in `gold_places`\n\n" + md_table(cats)
    )
    write("03_gold_tables.md", "Governed silver/gold tables in Unity Catalog", body)


def section_model(w: WorkspaceClient, sql: Sql, ctx: dict) -> None:
    path = f"/Volumes/{ctx['catalog']}/{ctx['schema']}/models/hex2vec"
    files = [{"file": f.path.rsplit("/", 1)[-1], "bytes": f.file_size,
              "modified": ms_to_iso(f.last_modified)}
             for f in w.files.list_directory_contents(path)]
    meta = json.loads(w.files.download(f"{path}/hex2vec_metadata.json").contents.read())
    cities = ", ".join(f"{c[1]} ({c[0]})" for c in meta["cities"])
    body = (
        f"Model artifacts in UC Volume `{path}`:\n\n" + md_table(files) +
        "\n## Training metadata (`hex2vec_metadata.json`)\n\n"
        f"- **Cities:** {len(meta['cities'])} — {cities}\n"
        f"- **H3 resolution:** {meta['resolution']}\n"
        f"- **Regions (H3 cells):** {meta['num_regions']:,}\n"
        f"- **Features (POIs + buildings):** {meta['num_features']:,}\n"
        f"- **Feature categories:** {len(meta['categories'])}\n"
        f"- **Encoder sizes:** {meta['encoder_sizes']} · **max epochs:** {meta['max_epochs']} · "
        f"**batch size:** {meta['batch_size']}\n"
        f"- **Saved at:** {meta['saved_at']}\n"
    )
    write("04_hex2vec_model.md", "Hex2Vec embedding model (trained by the ETL job)", body)


def section_genie(w: WorkspaceClient, sql: Sql, ctx: dict) -> None:
    fq = f"`{ctx['catalog']}`.`{ctx['schema']}`"
    space = sql.rows(f"SELECT config_value FROM {fq}.app_config WHERE config_key = 'GENIE_SPACE_ID'")
    if not space:
        raise RuntimeError("GENIE_SPACE_ID not found in app_config")
    space_id = space[0]["config_value"]
    questions = [
        f"How many {ctx['brand']} locations are there in {ctx['city']}?",
        f"Which brands have the most coffee shops in {ctx['city']}?",
        f"For the latest analysis, list the top 10 hexagons by opportunity score with their "
        f"cannibalization risk and nearest store distance.",
    ]
    parts = [f"- **Genie Space:** `{space_id}` "
             f"({ctx['host']}/genie/rooms/{space_id})\n"]
    for q in questions:
        parts.append(f"\n## Q: {q}\n")
        try:
            msg = w.genie.start_conversation_and_wait(space_id, q)
            for a in msg.attachments or []:
                if a.text and a.text.content:
                    parts.append(f"\n{a.text.content}\n")
                if a.query:
                    parts.append(f"\n**Generated SQL**\n\n```sql\n{a.query.query.strip()}\n```\n")
                    res = w.genie.get_message_attachment_query_result(
                        space_id, msg.conversation_id, msg.message_id, a.attachment_id,
                    ).statement_response
                    if res and res.result and res.manifest:
                        cols = [c.name for c in res.manifest.schema.columns]
                        rows = [dict(zip(cols, r)) for r in (res.result.data_array or [])[:10]]
                        parts.append("\n**Result (first 10 rows)**\n\n" + md_table(rows))
        except Exception as e:  # keep going; record the failure honestly
            parts.append(f"\n_Genie call failed: `{e}`_\n")
    write("05_genie_agent.md", "Genie Agent over the governed tables", "".join(parts))


def _app_session(w: WorkspaceClient) -> tuple[str, requests.Session]:
    app = w.apps.get(APP_NAME)
    s = requests.Session()
    s.headers.update(w.config.authenticate())
    return app.url.rstrip("/"), s


def section_app(w: WorkspaceClient, sql: Sql, ctx: dict) -> None:
    url, s = _app_session(w)
    cats = s.get(f"{url}/api/config", timeout=60).json()
    categories = [c for g in cats.get("category_groups", []) for c in g.get("categories", [])] \
        or cats.get("default_categories", [])
    req = {
        "country": ctx["country"], "city": ctx["city"], "resolution": 9,
        "categories": categories,
        "brand_input": {"mode": "brand_name", "value": ctx["brand"]},
        "enable_competition": True, "beta": 1.0,
        "include_buildings": True, "include_radiance": False, "catchment_km": 1.5,
    }
    t0 = time.time()
    result, steps = None, []
    with s.post(f"{url}/api/analyze", json=req, stream=True, timeout=900) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            ev = json.loads(line[5:])
            if ev["type"] == "progress":
                steps.append(f"{time.time() - t0:6.1f}s  {ev['step']}")
            elif ev["type"] == "result":
                result = ev["data"]
            elif ev["type"] == "error":
                raise RuntimeError(f"analyze failed: {ev['message']}")
    elapsed = time.time() - t0
    hexes = result["hexagons"]
    cands = [h for h in hexes if not h["is_brand_cell"]]
    key = "opportunity_score" if result["has_competition"] else "similarity"
    top = sorted(cands, key=lambda h: h[key] or 0, reverse=True)[:10]
    own = sum(1 for h in hexes if h["is_brand_cell"])
    high_cannib = sum(1 for h in cands if (h.get("cannibalization_risk") or 0) >= 0.5)

    sid = result["session_id"]
    detail = s.get(f"{url}/api/results/{sid}/hexagon/{top[0]['hex_id']}", timeout=300).json()
    added = s.post(f"{url}/api/shortlist", json={"session_id": sid, "hex_id": top[0]["hex_id"]}, timeout=60).json()
    s.patch(f"{url}/api/shortlist/{added['id']}",
            json={"status": "site_visit", "note": "Evidence run: top-ranked low-cannibalization cell"}, timeout=60)
    if len(top) > 1:
        s.post(f"{url}/api/shortlist", json={"session_id": sid, "hex_id": top[1]["hex_id"]}, timeout=60)
    shortlist = s.get(f"{url}/api/shortlist", params={"session_id": sid}, timeout=60).json()

    ctx["session_id"] = sid
    body = (
        f"- **App:** {url}\n- **Request:** brand `{ctx['brand']}` → {ctx['city']}, {ctx['country']} "
        f"(H3 res 9, competition β=1.0, catchment 1.5 km)\n"
        f"- **Session:** `{sid}` · **end-to-end time:** {elapsed:.1f}s\n"
        f"- **Hexagons scored:** {len(hexes):,} · existing brand cells: {own:,} · "
        f"candidates with ≥50% cannibalization: {high_cannib:,} ({100 * high_cannib / max(len(cands), 1):.1f}%)\n\n"
        "## Progress stream (SSE)\n\n```\n" + "\n".join(steps) + "\n```\n"
        f"\n## Top 10 candidate cells by {key.replace('_', ' ')}\n\n" + md_table(
            [{"hex_id": h["hex_id"], "address": h["address"], "similarity": h["similarity"],
              "opportunity": h.get("opportunity_score"), "cannibalization": h.get("cannibalization_risk"),
              "nearest_own_store_km": h.get("nearest_store_km"), "competitors": h.get("competitor_count")}
             for h in top]) +
        f"\n## Drill-down for the top cell (`/api/results/{{session}}/hexagon/{{hex}}`)\n\n"
        f"> {detail.get('explanation_summary', '')}\n\n"
        f"- cannibalization_risk: {detail.get('cannibalization_risk')} · nearest_store_km: "
        f"{detail.get('nearest_store_km')} · competitors in cell: "
        f"{(detail.get('competition') or {}).get('competitor_count', 0)}\n"
        "\n## Shortlist after adding two cells and moving one to *site visit* (`/api/shortlist`)\n\n" +
        md_table([{k: i.get(k) for k in ("id", "hex_id", "status", "note", "similarity",
                                         "cannibalization_risk", "nearest_store_km")} for i in shortlist])
    )
    write("06_app_analysis.md", "Live app run (Databricks App API)", body)


def section_lakebase(w: WorkspaceClient, sql: Sql, ctx: dict) -> None:
    import psycopg

    proj = next(p for p in w.postgres.list_projects() if p.name.endswith("site-selection-dev")
                or "site-selection" in p.name)
    branch = f"{proj.name}/branches/production"
    ep = next(iter(w.postgres.list_endpoints(parent=branch)))
    token = w.postgres.generate_database_credential(endpoint=ep.name).token
    user = w.current_user.me().user_name
    with psycopg.connect(host=ep.status.hosts.host, dbname="databricks_postgres", user=user,
                         password=token, sslmode="require") as conn:
        def q(sql_text, params=()):
            cur = conn.execute(sql_text, params)
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

        tables = q("""SELECT relname AS table_name, n_live_tup AS approx_rows
                      FROM pg_stat_user_tables WHERE schemaname = 'site_selection' ORDER BY 1""")
        sessions = q("""SELECT session_id, created_at, brand, city, n_hexagons,
                               pg_size_pretty(length(payload)::bigint) AS payload
                        FROM site_selection.sessions ORDER BY created_at DESC LIMIT 5""")
        t0 = time.perf_counter()
        top = q("""SELECT hex_id, round(opportunity_score::numeric, 4) AS opportunity,
                          round(cannibalization_risk::numeric, 3) AS cannibalization, nearest_store_km
                   FROM site_selection.session_hexagons
                   WHERE session_id = %s AND NOT is_brand_cell
                   ORDER BY opportunity_score DESC NULLS LAST LIMIT 5""",
                (ctx.get("session_id") or sessions[0]["session_id"],))
        lookup_ms = (time.perf_counter() - t0) * 1000
        shortlist = q("""SELECT id, hex_id, status, note, updated_at FROM site_selection.shortlist
                         ORDER BY updated_at DESC LIMIT 5""")
    body = (
        f"- **Project:** `{proj.name}` · branch `production` · endpoint `{ep.name}`\n"
        "- Queried directly with a short-lived OAuth credential "
        "(`w.postgres.generate_database_credential`).\n\n"
        "## Tables in the app-owned `site_selection` schema\n\n" + md_table(tables) +
        "\n## Most recent sessions (write-through from the app)\n\n" + md_table(sessions) +
        f"\n## Top-5 lookup for the evidence session ({lookup_ms:.0f} ms round-trip from laptop)\n\n" + md_table(top) +
        "\n## Shortlist rows\n\n" + md_table(shortlist)
    )
    write("07_lakebase.md", "Lakebase operational store", body)


SECTIONS = {
    "job": section_job, "pipeline": section_pipeline, "tables": section_tables,
    "model": section_model, "genie": section_genie, "app": section_app, "lakebase": section_lakebase,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", default="site_selection")
    ap.add_argument("--warehouse-id")
    ap.add_argument("--brand", default="Pret A Manger")
    ap.add_argument("--country", default="GB")
    ap.add_argument("--city", default="London")
    ap.add_argument("--only", nargs="*", choices=list(SECTIONS))
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile)
    wh = args.warehouse_id or next(
        x.id for x in w.warehouses.list() if x.enable_serverless_compute
    )
    ctx = {"catalog": args.catalog, "schema": args.schema, "brand": args.brand,
           "country": args.country, "city": args.city, "host": w.config.host.rstrip("/")}
    sql = Sql(w, wh)
    for name in args.only or list(SECTIONS):
        fn = SECTIONS[name]
        print(f"== {name}")
        try:
            fn(w, ctx) if name == "job" else fn(w, sql, ctx)
        except Exception as e:
            print(f"   FAILED: {e}")


if __name__ == "__main__":
    main()
