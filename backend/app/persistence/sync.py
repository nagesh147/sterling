"""
Phase 5b — position dual-write mirror + reconciliation.

When settings.use_sqlalchemy is ON, position writes to the raw-sqlite store are
mirrored into the SQLAlchemy store, and reconcile_positions() verifies the two
agree. All of this is GUARDED by the flag (default OFF) and FAIL-SAFE at the
call site (a mirror error never affects the primary sqlite write).

The ORM engine here uses resolve_database_url() — a dedicated file by default,
never the live sterling_paper.db. Point database_url at Postgres for production.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Dict, List, Optional

from sqlalchemy import select

from app.persistence.base import Base, make_engine
from app.persistence.session import make_session_factory, session_scope
from app.persistence.models import PositionRow

log = logging.getLogger(__name__)

_lock = threading.Lock()
_session_factory = None


def _factory():
    global _session_factory
    if _session_factory is None:
        with _lock:
            if _session_factory is None:
                engine = make_engine()
                Base.metadata.create_all(engine)
                _session_factory = make_session_factory(engine)
    return _session_factory


def reset_for_tests() -> None:
    """Drop the cached session factory so a new database_url takes effect."""
    global _session_factory
    _session_factory = None


def _row_from_pos(pos_dict: dict) -> PositionRow:
    return PositionRow(
        id=pos_dict["id"],
        underlying=pos_dict["underlying"],
        status=str(pos_dict["status"]),
        data=json.dumps(pos_dict, default=str),
        entry_ts=int(pos_dict["entry_timestamp_ms"]),
        updated_ts=int(time.time() * 1000),
        greeks_json=json.dumps(pos_dict["greeks"], default=str) if pos_dict.get("greeks") else None,
        notional=pos_dict.get("notional"),
        slippage_bps=pos_dict.get("slippage_bps"),
    )


def mirror_position_upsert(pos_dict: dict) -> None:
    with session_scope(_factory()) as s:
        s.merge(_row_from_pos(pos_dict))


def mirror_position_remove(pos_id: str) -> None:
    with session_scope(_factory()) as s:
        row = s.get(PositionRow, pos_id)
        if row is not None:
            s.delete(row)


def mirror_equity_snapshot(portfolio_value: float, drawdown: Optional[float] = None,
                           circuit_breaker_state: Optional[str] = None) -> None:
    from app.persistence.repositories import EquitySnapshotRepository
    with session_scope(_factory()) as s:
        EquitySnapshotRepository(s).add(portfolio_value, drawdown, circuit_breaker_state)


def reconcile_positions(sqlite_positions: List[dict]) -> Dict[str, Dict[str, Optional[str]]]:
    """Compare the raw-sqlite positions (list of dicts) against the ORM mirror.

    Returns per-id discrepancies of {sqlite: status, orm: status}. Empty = agree.
    """
    sqlite_map = {p["id"]: str(p["status"]) for p in sqlite_positions}
    with session_scope(_factory()) as s:
        orm_map = {r.id: r.status for r in s.scalars(select(PositionRow))}
    discrepancies: Dict[str, Dict[str, Optional[str]]] = {}
    for pid in set(sqlite_map) | set(orm_map):
        a, b = sqlite_map.get(pid), orm_map.get(pid)
        if a != b:
            discrepancies[pid] = {"sqlite": a, "orm": b}
    return discrepancies
