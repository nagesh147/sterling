"""
In-memory snapshot cache for market signal data.

SSE streams write here on every tick; the background alert poller reads
from here first and only calls the exchange if the entry is stale.
TTL is set slightly above the SSE signal-emit interval so a connected
stream always provides fresh data for the poller. Tunable via env:

    STERLING_SNAPSHOT_TTL_MS  (default 10000 = 10 s)

Enrichment preservation: the per-instrument SSE stream and background
alert checker write only basic fields (price, state, arrows). The put()
function preserves any enrichment (SL, TP, ATR, etc.) that was already
written by the background signal refresher (_compute_signal_item).
"""
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

try:
    _TTL_MS = int(os.environ.get("STERLING_SNAPSHOT_TTL_MS", "10000"))
except (TypeError, ValueError):
    _TTL_MS = 10_000

# Sentinel to distinguish "caller didn't pass" from "caller passed None"
_UNSET = object()


@dataclass
class SnapshotEntry:
    sym: str
    spot_price: float
    ivr: Optional[float]
    green_arrow: bool
    red_arrow: bool
    current_state: str
    computed_at_ms: int
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
    all_green: bool = False
    all_red: bool = False
    red_count: int = 0
    signal_score: float = 0.0
    signal_strength: str = "NONE"
    strategy: str = "legacy"
    track: str = ""


_cache: Dict[str, SnapshotEntry] = {}

# Fields that partial writers (SSE stream, alert checker) DON'T pass —
# we preserve their values from the previous cache entry.
_PRESERVE_FIELDS = (
    'direction', 'regime', 'score_long', 'score_short', 'exec_mode',
    'stop_price', 'target_price', 'atr', 'adx', 'atr_percentile', 'rsi',
    'squeezed', 'exec_confidence', 'all_green', 'all_red', 'red_count',
    'signal_score', 'signal_strength', 'strategy', 'track',
)


def put(
    sym: str,
    spot_price: float,
    ivr: Optional[float],
    green_arrow: bool,
    red_arrow: bool,
    current_state: str,
    direction = _UNSET,
    regime = _UNSET,
    score_long = _UNSET,
    score_short = _UNSET,
    exec_mode = _UNSET,
    stop_price = _UNSET,
    target_price = _UNSET,
    atr = _UNSET,
    adx = _UNSET,
    atr_percentile = _UNSET,
    rsi = _UNSET,
    squeezed = _UNSET,
    exec_confidence = _UNSET,
    all_green = _UNSET,
    all_red = _UNSET,
    red_count = _UNSET,
    signal_score = _UNSET,
    signal_strength = _UNSET,
    strategy = _UNSET,
    track = _UNSET,
) -> None:
    existing = _cache.get(sym)

    kwargs = dict(
        sym=sym,
        spot_price=spot_price,
        ivr=ivr,
        green_arrow=green_arrow,
        red_arrow=red_arrow,
        current_state=current_state,
        computed_at_ms=int(time.time() * 1000),
        direction=direction if direction is not _UNSET else (existing.direction if existing else "neutral"),
        regime=regime if regime is not _UNSET else (existing.regime if existing else ""),
        score_long=score_long if score_long is not _UNSET else (existing.score_long if existing else 0.0),
        score_short=score_short if score_short is not _UNSET else (existing.score_short if existing else 0.0),
        exec_mode=exec_mode if exec_mode is not _UNSET else (existing.exec_mode if existing else None),
        stop_price=stop_price if stop_price is not _UNSET else (existing.stop_price if existing else None),
        target_price=target_price if target_price is not _UNSET else (existing.target_price if existing else None),
        atr=atr if atr is not _UNSET else (existing.atr if existing else None),
        adx=adx if adx is not _UNSET else (existing.adx if existing else 0.0),
        atr_percentile=atr_percentile if atr_percentile is not _UNSET else (existing.atr_percentile if existing else 50.0),
        rsi=rsi if rsi is not _UNSET else (existing.rsi if existing else 50.0),
        squeezed=squeezed if squeezed is not _UNSET else (existing.squeezed if existing else False),
        exec_confidence=exec_confidence if exec_confidence is not _UNSET else (existing.exec_confidence if existing else 0.0),
        all_green=all_green if all_green is not _UNSET else (existing.all_green if existing else False),
        all_red=all_red if all_red is not _UNSET else (existing.all_red if existing else False),
        red_count=red_count if red_count is not _UNSET else (existing.red_count if existing else 0),
        signal_score=signal_score if signal_score is not _UNSET else (existing.signal_score if existing else 0.0),
        signal_strength=signal_strength if signal_strength is not _UNSET else (existing.signal_strength if existing else "NONE"),
        strategy=strategy if strategy is not _UNSET else (existing.strategy if existing else "legacy"),
        track=track if track is not _UNSET else (existing.track if existing else ""),
    )
    _cache[sym] = SnapshotEntry(**kwargs)


def get(sym: str) -> Optional[SnapshotEntry]:
    entry = _cache.get(sym)
    if entry and (time.time() * 1000 - entry.computed_at_ms) < _TTL_MS:
        return entry
    return None


def clear() -> None:
    _cache.clear()
