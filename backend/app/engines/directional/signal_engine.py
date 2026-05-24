"""STRATEGY STUB — 1H signal generation removed in the strategy reset.

The prior supertrend/RSI/squeeze confluence signal engine was stripped so a new
strategy can be built on a clean seam (preserved in git history on the
`strategy-v2` branch). `compute_signal` returns a neutral (no-trade) signal.

`_to_vwap_candles` is a pure VWAP chart transform (not decision logic) and is
preserved so the chart-overlay endpoint keeps rendering supertrend lines.

Implement the new signal logic here.
"""
from __future__ import annotations

from typing import Generator, List, Optional, Tuple

from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.directional.signal_weights import SignalThresholds

# Per-process memoisation cache for the (future) signal engine. Kept so test
# fixtures and any warm-cache callers can clear it; unused by the stub.
_SIGNAL_CACHE: dict = {}


def compute_signal(
    candles_1h: List[Candle],
    st_threshold: int = 3,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    thresholds: Optional[SignalThresholds] = None,
    regime_label: str = "",
) -> SignalResult:
    """Neutral signal: no trend, no arrows, zero scores (no strategy loaded)."""
    close = float(candles_1h[-1].close) if candles_1h else 0.0
    return SignalResult(
        trend=0,
        all_green=False,
        all_red=False,
        green_arrow=False,
        red_arrow=False,
        st_trends=[0, 0, 0],
        st_values=[0.0, 0.0, 0.0],
        close_1h=close,
        score_long=0.0,
        score_short=0.0,
        signal_strength="NONE",
        signal_score=0.0,
    )


def _to_vwap_candles(candles: List[Candle]) -> Generator[Candle, None, None]:
    """
    Pure VWAP transform (NOT strategy logic): replace close with cumulative
    session VWAP (reset at 00:00 UTC) and shift O/H/L by the same offset so
    ATR/supertrend stay proportional. Used by the chart-overlay endpoint.
    """
    sessions: dict = {}
    for c in candles:
        day_key = c.timestamp_ms // 86_400_000
        if day_key not in sessions:
            sessions[day_key] = {"cum_pv": 0.0, "cum_vol": 0.0}
        typical = (c.high + c.low + c.close) / 3.0
        sessions[day_key]["cum_pv"] += typical * c.volume
        sessions[day_key]["cum_vol"] += c.volume
        vwap = (
            sessions[day_key]["cum_pv"] / sessions[day_key]["cum_vol"]
            if sessions[day_key]["cum_vol"] > 0
            else c.close
        )
        offset = vwap - c.close
        yield Candle(
            timestamp_ms=c.timestamp_ms,
            open=c.open + offset,
            high=c.high + offset,
            low=c.low + offset,
            close=vwap,
            volume=c.volume,
        )
