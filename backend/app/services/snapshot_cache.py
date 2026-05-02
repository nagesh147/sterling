"""
In-memory snapshot cache for market signal data.

SSE streams write here on every tick; the background alert poller reads
from here first and only calls the exchange if the entry is stale.
TTL slightly exceeds the default SSE interval (30s) so a connected stream
always provides fresh data for the poller.
"""
import time
from dataclasses import dataclass
from typing import Dict, Optional

_TTL_MS = 45_000  # 45 s — fresh enough for 30 s SSE interval


@dataclass
class SnapshotEntry:
    sym: str
    spot_price: float
    ivr: Optional[float]
    green_arrow: bool
    red_arrow: bool
    current_state: str
    computed_at_ms: int


_cache: Dict[str, SnapshotEntry] = {}


def put(
    sym: str,
    spot_price: float,
    ivr: Optional[float],
    green_arrow: bool,
    red_arrow: bool,
    current_state: str,
) -> None:
    _cache[sym] = SnapshotEntry(
        sym=sym,
        spot_price=spot_price,
        ivr=ivr,
        green_arrow=green_arrow,
        red_arrow=red_arrow,
        current_state=current_state,
        computed_at_ms=int(time.time() * 1000),
    )


def get(sym: str) -> Optional[SnapshotEntry]:
    entry = _cache.get(sym)
    if entry and (time.time() * 1000 - entry.computed_at_ms) < _TTL_MS:
        return entry
    return None


def clear() -> None:
    _cache.clear()
