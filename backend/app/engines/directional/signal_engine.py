"""Directional 1H signal engine — real regime-following signals, honest scores.

Replaces the strategy-reset stub (a trivial EMA cross that stamped `score=85 /
"STRONG"` on every output) with the validated regime logic that works on crypto
(see docs/fullcycle_stress_test.md, DSR 0.394): ADX + SMA-slope regime →
momentum in trend, mean-reversion in range, with a score that VARIES with real
conviction (ADX strength / RSI extremity), not a constant. The edge is validated
on the futures payoff and is research-grade (DSR < 0.5, not deflation-provable) —
these are advisory signals, not a guarantee.

`_to_vwap_candles` is a pure VWAP chart transform (not decision logic), preserved
so the chart-overlay endpoint keeps rendering.
"""
from __future__ import annotations

from typing import Generator, List, Optional, Tuple

from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.directional.signal_weights import SignalThresholds
from app.engines.directional.indicators import (
    candles_to_df, adx14, rsi14, sma_slope,
)

# Per-process memoisation cache. Kept so test fixtures / warm-cache callers can
# clear it.
_SIGNAL_CACHE: dict = {}

_ADX_TREND = 25.0          # ADX above this = a real (tradable) trend
_MIN_BARS = 50             # need enough history for SMA(50)/ADX to be meaningful


def _none_signal(close: float = 0.0) -> SignalResult:
    return SignalResult(
        trend=0, all_green=False, all_red=False, green_arrow=False,
        red_arrow=False, st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
        close_1h=close, score_long=0.0, score_short=0.0,
        signal_strength="NONE", signal_score=0.0, rsi=50.0,
    )


def compute_signal(
    candles_1h: List[Candle],
    st_threshold: int = 3,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    thresholds: Optional[SignalThresholds] = None,
    regime_label: str = "",
) -> SignalResult:
    """Regime-following directional signal with an honest, varying score.

    Trend (ADX≥25): momentum — long if SMA slope up, short if down; score scales
    with ADX strength. Range (ADX<25): mean-reversion — long when RSI oversold,
    short when overbought; score scales with RSI extremity. Score in [0,100];
    strength STRONG≥75 / SIGNAL≥55 / NONE below.
    """
    if not candles_1h:
        return _none_signal()
    df = candles_to_df(candles_1h)
    close = float(df["close"].iloc[-1])
    if len(df) < _MIN_BARS:
        return _none_signal(close)

    adx = float(adx14(df).iloc[-1])
    rsi = float(rsi14(df["close"]).iloc[-1])
    slope = sma_slope(df["close"], window=50, lookback=5)
    ema9 = float(df["close"].ewm(span=9, adjust=False).mean().iloc[-1])
    ema21 = float(df["close"].ewm(span=21, adjust=False).mean().iloc[-1])
    fresh = (ema9 > ema21) if slope > 0 else (ema9 < ema21)

    trend = 0
    score = 0.0
    if adx >= _ADX_TREND and slope != 0.0:
        # Momentum: trade with the trend. Score rises with ADX strength.
        trend = 1 if slope > 0 else -1
        score = 50.0 + min(40.0, (adx - 20.0) * 2.0) + (8.0 if fresh else 0.0)
    else:
        # Range: mean-reversion. Score rises with how far RSI is from 50.
        if rsi < 35.0:
            trend = 1
            score = 50.0 + min(45.0, (35.0 - rsi) * 2.0)
        elif rsi > 65.0:
            trend = -1
            score = 50.0 + min(45.0, (rsi - 65.0) * 2.0)
        else:
            return _none_signal(close)

    score = round(max(0.0, min(100.0, score)), 1)
    strength = "STRONG" if score >= 75 else "SIGNAL" if score >= 55 else "NONE"
    if strength == "NONE":
        return _none_signal(close)

    score_long = score if trend == 1 else 0.0
    score_short = score if trend == -1 else 0.0
    return SignalResult(
        trend=trend,
        all_green=(trend == 1),
        all_red=(trend == -1),
        green_arrow=(trend == 1 and fresh),
        red_arrow=(trend == -1 and fresh),
        st_trends=[trend, trend, trend],
        st_values=[round(ema9, 2), round(ema21, 2),
                   round(float(df["close"].rolling(50).mean().iloc[-1]), 2)],
        close_1h=close,
        score_long=score_long,
        score_short=score_short,
        signal_strength=strength,
        signal_score=round(max(score_long, score_short), 1),
        rsi=round(rsi, 1),
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
