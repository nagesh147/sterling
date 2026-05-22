"""
In-memory snapshot cache for market signal data.

SSE streams write here on every tick; the background alert poller reads
from here first and only calls the exchange if the entry is stale.
TTL is set slightly above the SSE signal-emit interval so a connected
stream always provides fresh data for the poller. Tunable via env:

    STERLING_SNAPSHOT_TTL_MS  (default 10000 = 10 s)
"""
import os
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

# Default 10 s. Bumped up to 45 s historically for the legacy 30-s SSE
# interval; now matches a 5-s emit cadence with a 2× grace window.
try:
    _TTL_MS = int(os.environ.get("STERLING_SNAPSHOT_TTL_MS", "10000"))
except (TypeError, ValueError):
    _TTL_MS = 10_000


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
    # Raw trend booleans — used for poll-level edge detection in /signals
    all_green: bool = False
    all_red: bool = False
    # Algo-gating inputs (populated from SignalResult)
    # signal_score is the 0-20 confluence score (3-ST + RSI + squeeze + volume + HA)
    # signal_strength is "STRONG" when signal_score >= 15 (75%), "SIGNAL" >= 7, else "NONE"
    signal_score: float = 0.0
    signal_strength: str = "NONE"
    # Winning track name: "vcp" | "trend_following" | "mean_reversion" | ""
    track: str = ""


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
    all_green: bool = False,
    all_red: bool = False,
    signal_score: float = 0.0,
    signal_strength: str = "NONE",
    track: str = "",
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
        all_green=all_green,
        all_red=all_red,
        signal_score=signal_score,
        signal_strength=signal_strength,
        track=track,
    )


def get(sym: str) -> Optional[SnapshotEntry]:
    entry = _cache.get(sym)
    if entry and (time.time() * 1000 - entry.computed_at_ms) < _TTL_MS:
        return entry
    return None


def clear() -> None:
    _cache.clear()
