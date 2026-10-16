"""Lakebase (Postgres) operational store for live app state.

Delta tables in Unity Catalog stay the analytical record (Genie, history,
lineage). Lakebase holds what the running app needs at low latency and
must survive restarts / scale-out:

  sessions          one row per analysis run + a compact serialised result,
                    so hexagon drill-downs keep working after the app restarts
                    or a request lands on a different worker
  session_hexagons  the scored cells, queryable by score for the map and
                    for joining shortlist entries back to their scores
  shortlist         candidate sites a real-estate lead has starred, with a
                    status workflow and notes — read/write OLTP state that
                    does not belong in an append-only Delta table

When the app has no Lakebase resource attached (local dev without PG* env
vars) every function degrades to a no-op so the in-memory cache still works.
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import zipfile
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

import pandas as pd

if TYPE_CHECKING:
    from cache import PipelineResult

log = logging.getLogger(__name__)

PG_SCHEMA = os.getenv("LAKEBASE_SCHEMA", "site_selection")
SHORTLIST_STATUSES = ("candidate", "site_visit", "negotiating", "rejected")

# OAuth tokens for Lakebase are valid for 1 hour; refresh well before expiry.
_TOKEN_TTL_S = 40 * 60

_pool = None
_pool_lock = threading.Lock()
_token: dict[str, float | str] = {"value": "", "fetched_at": 0.0}
_schema_ready = False


def is_enabled() -> bool:
    return bool(os.getenv("PGHOST"))


def _endpoint_name() -> str:
    """Resolve the Lakebase endpoint resource path for credential minting."""
    ep = os.getenv("LAKEBASE_ENDPOINT", "")
    if ep:
        return ep
    branch = os.getenv("LAKEBASE_BRANCH", "")
    if not branch:
        raise RuntimeError("Set LAKEBASE_ENDPOINT or LAKEBASE_BRANCH for the app")
    from db import _get_client

    for e in _get_client().postgres.list_endpoints(parent=branch):
        if e.status and e.status.hosts and e.status.hosts.host == os.environ["PGHOST"]:
            return e.name
    raise RuntimeError(f"No Lakebase endpoint on {branch} matches PGHOST")


def _current_token() -> str:
    now = time.time()
    if not _token["value"] or now - float(_token["fetched_at"]) > _TOKEN_TTL_S:
        from db import _get_client

        cred = _get_client().postgres.generate_database_credential(endpoint=_endpoint_name())
        _token["value"] = cred.token
        _token["fetched_at"] = now
    return str(_token["value"])


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            import psycopg
            from psycopg_pool import ConnectionPool

            class _TokenConnection(psycopg.Connection):
                # Mint the password per physical connection so pooled
                # connections opened after a token rotation authenticate.
                @classmethod
                def connect(cls, conninfo: str = "", **kwargs):
                    kwargs["password"] = _current_token()
                    return super().connect(conninfo, **kwargs)

            _pool = ConnectionPool(
                connection_class=_TokenConnection,
                kwargs={
                    "host": os.environ["PGHOST"],
                    "port": int(os.getenv("PGPORT", "5432")),
                    "dbname": os.getenv("PGDATABASE", "databricks_postgres"),
                    "user": os.environ["PGUSER"],
                    "sslmode": os.getenv("PGSSLMODE", "require"),
                },
                min_size=1,
                max_size=5,
                max_lifetime=_TOKEN_TTL_S,
                check=ConnectionPool.check_connection,
                open=True,
            )
    return _pool


@contextmanager
def _conn() -> Iterator:
    with _get_pool().connection() as conn:
        yield conn


def ensure_schema() -> None:
    """Create the app-owned schema and tables (idempotent).

    Runs as the app's service principal, which therefore owns the schema —
    the SP only holds CAN_CONNECT_AND_CREATE and cannot use schemas created
    by someone else.
    """
    global _schema_ready
    if _schema_ready or not is_enabled():
        return
    s = PG_SCHEMA
    ddl = f"""
    CREATE SCHEMA IF NOT EXISTS {s};

    CREATE TABLE IF NOT EXISTS {s}.sessions (
        session_id     TEXT PRIMARY KEY,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        created_by     TEXT,
        brand          TEXT,
        country        TEXT,
        city           TEXT,
        h3_resolution  INT,
        analysis_mode  TEXT,
        n_hexagons     INT,
        payload        BYTEA NOT NULL
    );

    CREATE TABLE IF NOT EXISTS {s}.session_hexagons (
        session_id           TEXT NOT NULL REFERENCES {s}.sessions ON DELETE CASCADE,
        hex_id               TEXT NOT NULL,
        h3_cell              BIGINT NOT NULL,
        similarity           REAL,
        opportunity_score    REAL,
        cannibalization_risk REAL,
        nearest_store_km     REAL,
        competitor_count     INT,
        poi_density          INT,
        is_brand_cell        BOOLEAN,
        address              TEXT,
        lat                  DOUBLE PRECISION,
        lon                  DOUBLE PRECISION,
        PRIMARY KEY (session_id, hex_id)
    );
    CREATE INDEX IF NOT EXISTS session_hexagons_rank
        ON {s}.session_hexagons (session_id, opportunity_score DESC NULLS LAST, similarity DESC);

    CREATE TABLE IF NOT EXISTS {s}.shortlist (
        id          BIGSERIAL PRIMARY KEY,
        session_id  TEXT NOT NULL,
        hex_id      TEXT NOT NULL,
        brand       TEXT,
        country     TEXT,
        city        TEXT,
        address     TEXT,
        status      TEXT NOT NULL DEFAULT 'candidate'
                    CHECK (status IN {SHORTLIST_STATUSES!r}),
        note        TEXT NOT NULL DEFAULT '',
        created_by  TEXT NOT NULL DEFAULT '',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (session_id, hex_id, created_by)
    );
    CREATE INDEX IF NOT EXISTS shortlist_by_user ON {s}.shortlist (created_by, updated_at DESC);
    """
    with _conn() as conn:
        conn.execute(ddl)
    _schema_ready = True
    log.info("Lakebase schema %s ready", s)


# -- Session payload (de)serialisation ---------------------------------------
# DataFrames go to Parquet, everything else to JSON, bundled in one zip so a
# session is a single BYTEA value. No pickle: the payload is data, not code.

_FRAME_FIELDS = ("count_vectors", "scored", "competitor_pois", "brand_pois")


def _frame_to_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=True)
    return buf.getvalue()


def _serialise(pr: "PipelineResult") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _FRAME_FIELDS:
            df = getattr(pr, name)
            if df is not None:
                zf.writestr(f"{name}.parquet", _frame_to_bytes(df))
        zf.writestr("brand_avg.parquet", _frame_to_bytes(pr.brand_avg.to_frame("value")))
        zf.writestr("brand_cells.parquet", _frame_to_bytes(pr.brand_profile["cells"]))
        centre = pr.city_h3_cells_df[["center_lat", "center_lon"]] if not pr.city_h3_cells_df.empty else pd.DataFrame(columns=["center_lat", "center_lon"])
        zf.writestr("city_centre.parquet", _frame_to_bytes(centre.reset_index(drop=True)))
        zf.writestr("meta.json", json.dumps({
            "address_lookup": {str(k): v for k, v in pr.address_lookup.items()},
            "brand_locations": pr.brand_locations,
            "city_polygon_wkt": pr.city_polygon_wkt,
            "analysis_mode": pr.analysis_mode,
            "created_at": pr.created_at,
        }, default=str))
    return buf.getvalue()


def _deserialise(payload: bytes) -> dict:
    """Return PipelineResult constructor kwargs (the cache builds the object)."""
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = set(zf.namelist())

        def frame(name: str) -> pd.DataFrame | None:
            fn = f"{name}.parquet"
            return pd.read_parquet(io.BytesIO(zf.read(fn))) if fn in names else None

        meta = json.loads(zf.read("meta.json"))
        brand_avg = frame("brand_avg")["value"]
        brand_cells = frame("brand_cells")
        return dict(
            count_vectors=frame("count_vectors"),
            brand_avg=brand_avg,
            brand_profile={"avg": brand_avg, "cells": brand_cells},
            scored=frame("scored"),
            address_lookup={int(k): v for k, v in meta["address_lookup"].items()},
            brand_locations=meta["brand_locations"],
            city_h3_cells_df=frame("city_centre"),
            pois_df=pd.DataFrame(),
            competitor_pois=frame("competitor_pois"),
            city_polygon_wkt=meta["city_polygon_wkt"],
            analysis_mode=meta["analysis_mode"],
            brand_pois=frame("brand_pois"),
            created_at=meta["created_at"],
        )


# -- Sessions ------------------------------------------------------------------

def save_session(
    session_id: str,
    pr: "PipelineResult",
    *,
    created_by: str = "",
    brand: str = "",
    country: str = "",
    city: str = "",
    resolution: int | None = None,
) -> None:
    """Write-through an analysis result: compact payload + scored hexagons."""
    if not is_enabled():
        return
    import h3

    ensure_schema()
    s = PG_SCHEMA
    scored = pr.scored
    rows = []
    for r in scored.itertuples(index=False):
        cell = int(r.h3_cell)
        lat, lon = h3.cell_to_latlng(h3.int_to_str(cell))
        rows.append((
            session_id, h3.int_to_str(cell), cell,
            float(r.similarity),
            _opt_float(getattr(r, "opportunity_score", None)),
            _opt_float(getattr(r, "cannibalization_risk", None)),
            _opt_float(getattr(r, "nearest_store_km", None)),
            int(getattr(r, "competitor_count", 0) or 0),
            int(getattr(r, "poi_density", 0) or 0),
            bool(r.is_brand_cell),
            pr.address_lookup.get(cell, ""),
            lat, lon,
        ))

    t0 = time.time()
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {s}.sessions
                (session_id, created_by, brand, country, city, h3_resolution,
                 analysis_mode, n_hexagons, payload)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO NOTHING""",
            (session_id, created_by, brand, country, city, resolution,
             pr.analysis_mode, len(rows), _serialise(pr)),
        )
        with cur.copy(
            f"""COPY {s}.session_hexagons
                (session_id, hex_id, h3_cell, similarity, opportunity_score,
                 cannibalization_risk, nearest_store_km, competitor_count,
                 poi_density, is_brand_cell, address, lat, lon) FROM STDIN"""
        ) as copy:
            for row in rows:
                copy.write_row(row)
    log.info("Lakebase: saved session %s (%d hexagons) in %.2fs", session_id, len(rows), time.time() - t0)


def load_session(session_id: str) -> dict | None:
    if not is_enabled():
        return None
    ensure_schema()
    with _conn() as conn:
        row = conn.execute(
            f"SELECT payload FROM {PG_SCHEMA}.sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    log.info("Lakebase: rehydrated session %s", session_id)
    return _deserialise(bytes(row[0]))


def _opt_float(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return float(v)


# -- Shortlist -----------------------------------------------------------------

_SHORTLIST_COLS = """
    sl.id, sl.session_id, sl.hex_id, sl.brand, sl.country, sl.city, sl.address,
    sl.status, sl.note, sl.created_by, sl.created_at, sl.updated_at,
    h.similarity, h.opportunity_score, h.cannibalization_risk, h.nearest_store_km,
    h.competitor_count, h.lat, h.lon
"""


def _shortlist_rows(cur) -> list[dict]:
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def list_shortlist(created_by: str, session_id: str | None = None) -> list[dict]:
    ensure_schema()
    s = PG_SCHEMA
    where = "sl.created_by = %s"
    params: list = [created_by]
    if session_id:
        where += " AND sl.session_id = %s"
        params.append(session_id)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT {_SHORTLIST_COLS}
                FROM {s}.shortlist sl
                LEFT JOIN {s}.session_hexagons h
                  ON h.session_id = sl.session_id AND h.hex_id = sl.hex_id
                WHERE {where}
                ORDER BY sl.updated_at DESC""",
            params,
        )
        return _shortlist_rows(cur)


def add_to_shortlist(
    created_by: str, session_id: str, hex_id: str, note: str = "",
) -> dict:
    ensure_schema()
    s = PG_SCHEMA
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO {s}.shortlist
                    (session_id, hex_id, brand, country, city, address, note, created_by)
                SELECT %(sid)s, %(hex)s, se.brand, se.country, se.city,
                       COALESCE(h.address, ''), %(note)s, %(by)s
                FROM {s}.sessions se
                LEFT JOIN {s}.session_hexagons h
                  ON h.session_id = se.session_id AND h.hex_id = %(hex)s
                WHERE se.session_id = %(sid)s
                ON CONFLICT (session_id, hex_id, created_by)
                DO UPDATE SET updated_at = now()
                RETURNING id""",
            {"sid": session_id, "hex": hex_id, "note": note, "by": created_by},
        )
        row = cur.fetchone()
        if row is None:
            raise KeyError(f"Unknown session {session_id}")
        cur.execute(
            f"""SELECT {_SHORTLIST_COLS} FROM {s}.shortlist sl
                LEFT JOIN {s}.session_hexagons h
                  ON h.session_id = sl.session_id AND h.hex_id = sl.hex_id
                WHERE sl.id = %s""",
            (row[0],),
        )
        return _shortlist_rows(cur)[0]


def update_shortlist(
    created_by: str, item_id: int, status: str | None = None, note: str | None = None,
) -> dict | None:
    if status is not None and status not in SHORTLIST_STATUSES:
        raise ValueError(f"status must be one of {SHORTLIST_STATUSES}")
    ensure_schema()
    s = PG_SCHEMA
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""UPDATE {s}.shortlist
                SET status = COALESCE(%s, status),
                    note = COALESCE(%s, note),
                    updated_at = now()
                WHERE id = %s AND created_by = %s
                RETURNING id""",
            (status, note, item_id, created_by),
        )
        if cur.fetchone() is None:
            return None
        cur.execute(
            f"""SELECT {_SHORTLIST_COLS} FROM {s}.shortlist sl
                LEFT JOIN {s}.session_hexagons h
                  ON h.session_id = sl.session_id AND h.hex_id = sl.hex_id
                WHERE sl.id = %s""",
            (item_id,),
        )
        return _shortlist_rows(cur)[0]


def remove_from_shortlist(created_by: str, item_id: int) -> bool:
    ensure_schema()
    with _conn() as conn:
        cur = conn.execute(
            f"DELETE FROM {PG_SCHEMA}.shortlist WHERE id = %s AND created_by = %s",
            (item_id, created_by),
        )
        return cur.rowcount > 0
