"""
P&L snapshot history per paper position.
Recorded each time a position is monitored.
Persists to SQLite so sparklines survive server restarts.
"""
import json
from collections import deque
from typing import Dict, Deque, List, Optional
from pydantic import BaseModel

from app.core.logging import get_logger

log = get_logger(__name__)

MAX_SNAPSHOTS = 200


class PnLSnapshot(BaseModel):
    timestamp_ms: int
    spot_price: float
    estimated_pnl: float
    current_dte: int


_history: Dict[str, Deque[PnLSnapshot]] = {}
_loaded = False


# ─── SQLite persistence ───────────────────────────────────────────────────────

def _ensure_table() -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS pnl_history (
                    pos_id     TEXT NOT NULL,
                    snapshots  TEXT NOT NULL DEFAULT '[]',
                    updated_ms INTEGER NOT NULL,
                    PRIMARY KEY (pos_id)
                )
            """)
    except Exception as exc:
        log.warning("pnl_history table init failed: %s", exc)


def _persist_pos(pos_id: str) -> None:
    from app.services import db
    if not db._available:
        return
    snaps = [s.model_dump() for s in _history.get(pos_id, [])]
    try:
        with db._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO pnl_history (pos_id, snapshots, updated_ms) VALUES (?, ?, ?)",
                (pos_id, json.dumps(snaps), snaps[-1]["timestamp_ms"] if snaps else 0),
            )
    except Exception as exc:
        log.warning("pnl_history persist failed for %s: %s", pos_id, exc)


def _load_all() -> None:
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            rows = c.execute("SELECT pos_id, snapshots FROM pnl_history").fetchall()
        for r in rows:
            snaps = json.loads(r["snapshots"] or "[]")
            q: Deque[PnLSnapshot] = deque(maxlen=MAX_SNAPSHOTS)
            for s in snaps:
                try:
                    q.append(PnLSnapshot(**s))
                except Exception:
                    continue
            if q:
                _history[r["pos_id"]] = q
    except Exception as exc:
        log.warning("pnl_history load failed: %s", exc)


def bootstrap() -> None:
    global _loaded
    if _loaded:
        return
    _ensure_table()
    _load_all()
    if _history:
        log.info("Loaded P&L history for %d positions from DB", len(_history))
    _loaded = True


# ─── Public API ───────────────────────────────────────────────────────────────

def record(pos_id: str, spot: float, estimated_pnl: float, dte: int, timestamp_ms: int) -> None:
    if pos_id not in _history:
        _history[pos_id] = deque(maxlen=MAX_SNAPSHOTS)
    _history[pos_id].append(PnLSnapshot(
        timestamp_ms=timestamp_ms,
        spot_price=spot,
        estimated_pnl=estimated_pnl,
        current_dte=dte,
    ))
    _persist_pos(pos_id)


def get_history(pos_id: str) -> List[PnLSnapshot]:
    return list(_history.get(pos_id, []))


def clear(pos_id: Optional[str] = None) -> None:
    if pos_id:
        _history.pop(pos_id, None)
    else:
        _history.clear()
