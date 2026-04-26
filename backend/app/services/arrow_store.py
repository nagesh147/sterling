"""
Session-scoped arrow event store.
Records green/red arrow events from SSE stream and run-once evaluations.
"""
from collections import deque
from typing import Dict, Deque, List, Optional
from pydantic import BaseModel

MAX_ARROWS = 200


class ArrowEvent(BaseModel):
    underlying: str
    arrow_type: str       # "green" | "red"
    spot_price: float
    direction: str        # "long" | "short"
    state: str
    source: str           # "stream" | "run_once"
    timestamp_ms: int


_store: Dict[str, Deque[ArrowEvent]] = {}


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
    _store[underlying].append(
        ArrowEvent(
            underlying=underlying,
            arrow_type=arrow_type,
            spot_price=spot_price,
            direction=direction,
            state=state,
            source=source,
            timestamp_ms=timestamp_ms,
        )
    )


def get_arrows(underlying: str) -> List[ArrowEvent]:
    return list(reversed(list(_store.get(underlying, []))))  # newest first


def get_all() -> List[ArrowEvent]:
    all_arrows = []
    for events in _store.values():
        all_arrows.extend(events)
    return sorted(all_arrows, key=lambda e: e.timestamp_ms, reverse=True)


def clear(underlying: Optional[str] = None) -> None:
    if underlying:
        _store.pop(underlying, None)
    else:
        _store.clear()
