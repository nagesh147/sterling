"""Selector-decision audit log.

Every `selector.decide()` result (whether executed or not) is appended
here so the operator can review what the selector saw, what it picked,
and—when executed—how the position resolved. Foundation for the 7-day
observation practice recommended before flipping each strategy's
`profile.enabled=True` in production.

Storage: in-memory ring buffer (cap 5000 entries) + write-through to
SQLite via the existing `app/services/db.py` infrastructure. The ring
buffer covers hot reads (FE table); SQLite persists across restarts.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Deque, Optional

from app.services import db as _db

log = logging.getLogger(__name__)


AUDIT_RING_MAX = 5000

_RING: Deque[dict] = deque(maxlen=AUDIT_RING_MAX)
_LOCK = threading.RLock()
_INITIALISED = False


def _init_table() -> None:
    """Create the audit table on first use. Reuses the existing SQLite
    connection from app/services/db.py."""
    global _INITIALISED
    if _INITIALISED:
        return
    try:
        con = sqlite3.connect(_db._DB_PATH)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS derivatives_audit (
              audit_id    TEXT PRIMARY KEY,
              ts_ms       INTEGER NOT NULL,
              strategy    TEXT NOT NULL,
              underlying  TEXT NOT NULL,
              status      TEXT NOT NULL,
              instrument  TEXT,
              chosen_json TEXT,
              signal_json TEXT,
              market_json TEXT,
              executed    INTEGER NOT NULL DEFAULT 0,
              exit_pnl    REAL,
              exit_ts_ms  INTEGER
            )
            """
        )
        con.commit()
        con.close()
        _INITIALISED = True
    except Exception as exc:
        log.warning("derivatives_audit table init failed: %s — audit log will be in-memory only", exc)


@dataclass
class AuditEntry:
    audit_id: str
    ts_ms: int
    strategy: str
    underlying: str
    status: str                         # mirrors DecisionStatus.value
    instrument: Optional[str] = None    # "futures" | "options" when chosen
    chosen_json: Optional[str] = None
    signal_json: Optional[str] = None
    market_json: Optional[str] = None
    executed: bool = False
    exit_pnl: Optional[float] = None
    exit_ts_ms: Optional[int] = None


def _to_dict(entry: AuditEntry) -> dict:
    d = asdict(entry)
    d["executed"] = 1 if entry.executed else 0
    return d


def record(
    *,
    decision: Any,                      # DerivativesDecision but typed-as-Any to avoid circular import
    signal: Any,                        # SignalContext
    market: Any,                        # MarketContext
) -> str:
    """Append one entry; returns the audit_id so /execute can update
    `executed=1` later."""
    _init_table()
    import uuid
    aid = uuid.uuid4().hex
    entry = AuditEntry(
        audit_id=aid,
        ts_ms=int(time.time() * 1000),
        strategy=getattr(signal, "strategy", ""),
        underlying=getattr(signal, "underlying", ""),
        status=str(getattr(getattr(decision, "status", ""), "value", getattr(decision, "status", ""))),
        instrument=(getattr(getattr(decision, "chosen", None), "instrument_type", None)
                    if getattr(decision, "chosen", None) else None),
        chosen_json=_safe_json(getattr(decision, "chosen", None)),
        signal_json=_safe_json(signal),
        market_json=_safe_json(market),
    )
    with _LOCK:
        _RING.append(_to_dict(entry))
    _persist(entry)
    return aid


def mark_executed(audit_id: str) -> None:
    """Flag the entry as executed so the FE can show 'PAPER/LIVE filled'
    status. PnL gets filled on close via `record_exit`."""
    _init_table()
    with _LOCK:
        for d in _RING:
            if d["audit_id"] == audit_id:
                d["executed"] = 1
                break
    try:
        con = sqlite3.connect(_db._DB_PATH)
        con.execute("UPDATE derivatives_audit SET executed=1 WHERE audit_id=?", (audit_id,))
        con.commit()
        con.close()
    except Exception:
        pass


def record_exit(audit_id: str, exit_pnl: float, exit_ts_ms: Optional[int] = None) -> None:
    """Fill in the exit PnL when the position closes. Lets the operator
    compute per-strategy hit-rate, R-multiple distribution, etc. without
    cross-referencing paper_store."""
    _init_table()
    ts = exit_ts_ms or int(time.time() * 1000)
    with _LOCK:
        for d in _RING:
            if d["audit_id"] == audit_id:
                d["exit_pnl"] = exit_pnl
                d["exit_ts_ms"] = ts
                break
    try:
        con = sqlite3.connect(_db._DB_PATH)
        con.execute(
            "UPDATE derivatives_audit SET exit_pnl=?, exit_ts_ms=? WHERE audit_id=?",
            (exit_pnl, ts, audit_id),
        )
        con.commit()
        con.close()
    except Exception:
        pass


def list_recent(
    *, strategy: Optional[str] = None, underlying: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    with _LOCK:
        rows = list(_RING)
    if strategy:
        rows = [r for r in rows if r["strategy"] == strategy]
    if underlying:
        rows = [r for r in rows if r["underlying"] == underlying.upper()]
    return rows[-limit:][::-1]          # most recent first


def clear_for_tests() -> None:
    with _LOCK:
        _RING.clear()


# ── internals ──────────────────────────────────────────────────────────


def _safe_json(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    try:
        if hasattr(obj, "model_dump"):
            return json.dumps(obj.model_dump(mode="json"), default=str)
        if hasattr(obj, "__dict__"):
            return json.dumps(obj.__dict__, default=str)
        return json.dumps(obj, default=str)
    except Exception:
        return None


def _persist(entry: AuditEntry) -> None:
    """Best-effort SQLite write-through. Never raises."""
    try:
        con = sqlite3.connect(_db._DB_PATH)
        con.execute(
            """INSERT INTO derivatives_audit
                (audit_id, ts_ms, strategy, underlying, status, instrument,
                 chosen_json, signal_json, market_json, executed, exit_pnl, exit_ts_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry.audit_id, entry.ts_ms, entry.strategy, entry.underlying,
             entry.status, entry.instrument, entry.chosen_json,
             entry.signal_json, entry.market_json, 0, None, None),
        )
        con.commit()
        con.close()
    except Exception as exc:
        log.debug("derivatives_audit persist failed (in-memory only): %s", exc)
