"""Convert historical/live-neutral Kite Candle objects into Adaptive Edge replay bars.

This adapter is intentionally deterministic and causal. At index i, every
feature uses candles at or before i only. It is the boundary between market
candle data and the reconstructed Adaptive Edge model.
"""
from __future__ import annotations

from math import sqrt
from statistics import mean, pstdev
from typing import Sequence

from app.schemas.market import Candle

from .backtest import ReplayBar
from .model import MarketFeatures


def _returns(closes: Sequence[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes)) if closes[i - 1] > 0]


def _atr(candles: Sequence[Candle], window: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    values: list[float] = []
    start = max(1, len(candles) - window)
    for i in range(start, len(candles)):
        prev = candles[i - 1].close
        if prev <= 0:
            continue
        values.append(max(
            candles[i].high - candles[i].low,
            abs(candles[i].high - prev),
            abs(candles[i].low - prev),
        ))
    return mean(values) if values else 0.0


def _normalized_return(closes: Sequence[float], bars: int, scale: float) -> float:
    if len(closes) <= bars or closes[-bars - 1] <= 0 or scale <= 0:
        return 0.0
    return max(-1.0, min(1.0, (closes[-1] / closes[-bars - 1] - 1.0) / scale))


def build_replay_bars(candles: Sequence[Candle]) -> list[ReplayBar]:
    """Build causally available ReplayBars from chronological Candle data."""
    if not candles:
        return []
    ordered = sorted(candles, key=lambda c: c.timestamp_ms)
    result: list[ReplayBar] = []

    for i in range(len(ordered)):
        history = ordered[: i + 1]
        close = history[-1].close
        if close <= 0:
            continue
        closes = [c.close for c in history]
        atr = _atr(history)
        scale = max(atr / close, 1e-6)
        trend = _normalized_return(closes, 20, scale)
        momentum = _normalized_return(closes, 5, scale)

        volumes = [max(c.volume, 0.0) for c in history[-20:]]
        current_volume = volumes[-1] if volumes else 0.0
        avg_volume = mean(volumes[:-1]) if len(volumes) > 1 else current_volume
        relative_volume = max(-1.0, min(1.0, current_volume / avg_volume - 1.0)) if avg_volume > 0 else 0.0

        rets = _returns(closes[-30:])
        short_vol = pstdev(rets[-5:]) if len(rets) >= 5 else 0.0
        long_vol = pstdev(rets) if len(rets) >= 2 else short_vol
        volatility_expansion = max(-1.0, min(1.0, short_vol / long_vol - 1.0)) if long_vol > 0 else 0.0

        confidence = min(1.0, len(history) / 30.0)
        expected_move = atr if atr > 0 else close * 0.005
        stale = i > 0 and ordered[i].timestamp_ms <= ordered[i - 1].timestamp_ms

        result.append(ReplayBar(
            close=close,
            spread_bps=5.0,
            atr=expected_move,
            features=MarketFeatures(
                trend=trend,
                momentum=momentum,
                relative_volume=relative_volume,
                volatility_expansion=volatility_expansion,
                expected_move=expected_move,
                confidence=confidence,
                stale=stale,
                late_session=False,
            ),
        ))
    return result
