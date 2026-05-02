"""
Rolling evaluation history per underlying.
Writes each new snapshot to SQLite and rehydrates on startup.
"""
import json
import os
from collections import deque
from typing import Dict, Deque, List, Any

_DEFAULT_CAP = int(os.environ.get("EVAL_HISTORY_CAP", "50"))

_history: Dict[str, Deque[dict]] = {}
_cap: int = _DEFAULT_CAP


def set_cap(n: int) -> None:
    global _cap, _history
    _cap = max(10, min(500, n))
    # Trim existing queues to new cap
    for sym in list(_history.keys()):
        _history[sym] = deque(list(_history[sym])[-_cap:], maxlen=_cap)


def get_cap() -> int:
    return _cap


def bootstrap() -> None:
    """Load persisted eval history from SQLite at startup."""
    from app.services import db
    if not db._available:
        return
    try:
        with db._conn() as c:
            rows = c.execute(
                "SELECT underlying, data FROM signal_history ORDER BY timestamp_ms ASC"
            ).fetchall()
        by_sym: Dict[str, List[dict]] = {}
        for r in rows:
            sym = r["underlying"]
            try:
                entry = json.loads(r["data"])
            except Exception:
                continue
            by_sym.setdefault(sym, []).append(entry)
        for sym, entries in by_sym.items():
            _history[sym] = deque(entries[-_cap:], maxlen=_cap)
    except Exception:
        pass


def record(underlying: str, result_dict: dict) -> None:
    if underlying not in _history:
        _history[underlying] = deque(maxlen=_cap)
    _history[underlying].append(result_dict)
    _persist(underlying, result_dict)


def _persist(underlying: str, entry: dict) -> None:
    from app.services import db
    if not db._available:
        return
    try:
        ts = entry.get("timestamp_ms", 0)
        with db._conn() as c:
            c.execute(
                "INSERT INTO signal_history (underlying, data, timestamp_ms) VALUES (?, ?, ?)",
                (underlying, json.dumps(entry), ts),
            )
            # Prune old rows beyond cap (keep latest _cap per underlying)
            c.execute("""
                DELETE FROM signal_history
                WHERE underlying = ?
                  AND id NOT IN (
                      SELECT id FROM signal_history
                      WHERE underlying = ?
                      ORDER BY timestamp_ms DESC
                      LIMIT ?
                  )
            """, (underlying, underlying, _cap))
    except Exception:
        pass


def get_history(underlying: str) -> List[dict]:
    return list(_history.get(underlying, []))


def clear(underlying: str | None = None) -> None:
    if underlying:
        _history.pop(underlying, None)
    else:
        _history.clear()
