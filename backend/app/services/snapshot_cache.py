"""
In-memory snapshot cache for market signal data.

SSE streams write here on every tick; the background alert poller reads
from here first and only calls the exchange if the entry is stale.
TTL slightly exceeds the default SSE interval (30s) so a connected stream
always provides fresh data for the poller.
"""
import time
from dataclasses import dataclass, field
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
    # Signal enrichment fields (populated by /signals live computation)
    direction: str = "neutral"
    regime: str = ""
    score_long: float = 0.0
    score_short: float = 0.0
    exec_mode: Optional[str] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    atr: Optional[float] = None
    adx: float = 0.0
    atr_percentile: float = 50.0
    rsi: float = 50.0
    squeezed: bool = False
    exec_confidence: float = 0.0


_cache: Dict[str, SnapshotEntry] = {}


def put(
    sym: str,
    spot_price: float,
    ivr: Optional[float],
    green_arrow: bool,
    red_arrow: bool,
    current_state: str,
    # Optional enrichment
    direction: str = "neutral",
    regime: str = "",
    score_long: float = 0.0,
    score_short: float = 0.0,
    exec_mode: Optional[str] = None,
    stop_price: Optional[float] = None,
    target_price: Optional[float] = None,
    atr: Optional[float] = None,
    adx: float = 0.0,
    atr_percentile: float = 50.0,
    rsi: float = 50.0,
    squeezed: bool = False,
    exec_confidence: float = 0.0,
) -> None:
    _cache[sym] = SnapshotEntry(
        sym=sym,
        spot_price=spot_price,
        ivr=ivr,
        green_arrow=green_arrow,
        red_arrow=red_arrow,
        current_state=current_state,
        computed_at_ms=int(time.time() * 1000),
        direction=direction,
        regime=regime,
        score_long=score_long,
        score_short=score_short,
        exec_mode=exec_mode,
        stop_price=stop_price,
        target_price=target_price,
        atr=atr,
        adx=adx,
        atr_percentile=atr_percentile,
        rsi=rsi,
        squeezed=squeezed,
        exec_confidence=exec_confidence,
    )


def get(sym: str) -> Optional[SnapshotEntry]:
    entry = _cache.get(sym)
    if entry and (time.time() * 1000 - entry.computed_at_ms) < _TTL_MS:
        return entry
    return None


def clear() -> None:
    _cache.clear()
