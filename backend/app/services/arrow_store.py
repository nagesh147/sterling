"""
Session-scoped arrow event store with TTL pruning.
Records green/red arrow events from SSE stream and run-once evaluations.
"""
import os
import time
from collections import deque
from typing import Dict, Deque, List, Optional
from pydantic import BaseModel

MAX_ARROWS = 200
_ARROW_TTL_HOURS = int(os.environ.get("ARROW_TTL_HOURS", "168"))  # 7-day default


class ArrowEvent(BaseModel):
    underlying: str
    arrow_type: str       # "green" | "red"
    spot_price: float
    direction: str        # "long" | "short"
    state: str
    source: str           # "stream" | "run_once"
    timestamp_ms: int


_store: Dict[str, Deque[ArrowEvent]] = {}
_bootstrapped = False


def bootstrap() -> None:
    """Load persisted arrows from SQLite into the in-memory store on startup."""
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True
    try:
        from app.services import db
        rows = db.load_arrows(limit=500, ttl_hours=_ARROW_TTL_HOURS)
        for r in rows:
            try:
                evt = ArrowEvent(
                    underlying=r["underlying"],
                    arrow_type=r["arrow_type"],
                    spot_price=r["spot_price"],
                    direction=r["direction"],
                    state=r["state"],
                    source=r["source"],
                    timestamp_ms=r["timestamp_ms"],
                )
                und = r["underlying"]
                if und not in _store:
                    _store[und] = deque(maxlen=MAX_ARROWS)
                _store[und].append(evt)
            except Exception:
                continue
    except Exception:
        pass


def _prune(underlying: str) -> None:
    """Remove events older than ARROW_TTL_HOURS for one underlying."""
    if underlying not in _store:
        return
    cutoff_ms = int((time.time() - _ARROW_TTL_HOURS * 3_600) * 1_000)
    kept = [e for e in _store[underlying] if e.timestamp_ms >= cutoff_ms]
    _store[underlying] = deque(kept, maxlen=MAX_ARROWS)


def record(
    underlying: str,
    arrow_type: str,
    spot_price: float,
    direction: str,
    state: str,
    timestamp_ms: int,
    source: str = "stream",
) -> None:
    if underlying not in _store:
        _store[underlying] = deque(maxlen=MAX_ARROWS)
    evt = ArrowEvent(
        underlying=underlying,
        arrow_type=arrow_type,
        spot_price=spot_price,
        direction=direction,
        state=state,
        source=source,
        timestamp_ms=timestamp_ms,
    )
    _store[underlying].append(evt)
    _prune(underlying)
    # Persist to SQLite so history survives restarts
    try:
        from app.services import db
        db.persist_arrow(
            underlying=underlying,
            arrow_type=arrow_type,
            spot_price=spot_price,
            direction=direction,
            state=state,
            source=source,
            timestamp_ms=timestamp_ms,
        )
    except Exception:
        pass


def get_arrows(underlying: str) -> List[ArrowEvent]:
    _prune(underlying)
    return list(reversed(list(_store.get(underlying, []))))  # newest first


def get_all() -> List[ArrowEvent]:
    for sym in list(_store.keys()):
        _prune(sym)
    all_arrows = []
    for events in _store.values():
        all_arrows.extend(events)
    return sorted(all_arrows, key=lambda e: e.timestamp_ms, reverse=True)


def clear(underlying: Optional[str] = None) -> None:
    if underlying:
        _store.pop(underlying, None)
    else:
        _store.clear()
