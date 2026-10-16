"""Result cache for pipeline outputs: in-memory, backed by Lakebase.

Keyed by session_id so the frontend can query any hexagon's
fingerprint on demand after a pipeline run completes. The in-process
dict is a hot cache only; Lakebase is the durable copy, so a session
survives app restarts and eviction (see lakebase.py).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    count_vectors: pd.DataFrame
    brand_avg: pd.Series
    brand_profile: dict
    scored: pd.DataFrame
    address_lookup: dict[int, str]
    brand_locations: list[dict]
    city_h3_cells_df: pd.DataFrame
    pois_df: pd.DataFrame
    competitor_pois: pd.DataFrame | None
    city_polygon_wkt: str | None
    analysis_mode: str = "brand"
    brand_pois: pd.DataFrame | None = None
    created_at: float = field(default_factory=time.time)

    def compact(self) -> None:
        """Release large DataFrames that are only needed during analysis."""
        self.pois_df = pd.DataFrame()
        self.city_h3_cells_df = pd.DataFrame()
        self.brand_pois = None


_lock = threading.Lock()
_store: dict[str, PipelineResult] = {}

MAX_SESSIONS = 20
TTL_SECONDS = 3600


def save(result: PipelineResult) -> str:
    session_id = uuid.uuid4().hex[:12]
    with _lock:
        _store[session_id] = result
        _evict()
    return session_id


def get(session_id: str) -> PipelineResult | None:
    with _lock:
        hit = _store.get(session_id)
    if hit is not None:
        return hit
    try:
        import lakebase

        fields = lakebase.load_session(session_id)
    except Exception:
        log.exception("Lakebase lookup failed for session %s", session_id)
        return None
    if fields is None:
        return None
    # Re-stamp so the in-memory TTL doesn't evict it straight away.
    restored = PipelineResult(**{**fields, "created_at": time.time()})
    with _lock:
        _store[session_id] = restored
        _evict()
    return restored


def _evict() -> None:
    now = time.time()
    expired = [k for k, v in _store.items() if now - v.created_at > TTL_SECONDS]
    for k in expired:
        del _store[k]
    while len(_store) > MAX_SESSIONS:
        oldest = min(_store, key=lambda k: _store[k].created_at)
        del _store[oldest]
