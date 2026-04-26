import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import ExecTimingResult, ExecMode, SignalResult
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.supertrend import compute_supertrend


def assess_timing(
    candles_15m: List[Candle],
    signal: SignalResult,
    atr_multiplier: float = 1.5,
) -> ExecTimingResult:
    if len(candles_15m) < 20:
        return ExecTimingResult(
            mode=ExecMode.WAIT,
            confidence=0.0,
            reason="Insufficient 15m candles",
        )

    h = np.array([c.high for c in candles_15m], dtype=np.float64)
    l = np.array([c.low for c in candles_15m], dtype=np.float64)
    c = np.array([c.close for c in candles_15m], dtype=np.float64)

    atr = compute_atr(h, l, c, 14)
    _, st_fast = compute_supertrend(h, l, c, 7, 3.0)

    current_close = c[-1]
    current_atr = atr[-1]
    st_level = 0.0

    # Estimate ST(7,3) support/resistance level
    # Approximate: find the trend value and extrapolate from recent closes
    st_trend = int(st_fast[-1])

    # Pullback: close within 1 ATR of fast ST line (use low for longs, high for shorts)
    recent_range = h[-5:] - l[-5:]
    avg_range = float(np.mean(recent_range)) if len(recent_range) > 0 else current_atr

    # Continuation: price extending beyond recent range + ATR
    prev_5_high = float(np.max(h[-6:-1])) if len(h) >= 6 else h[-1]
    prev_5_low = float(np.min(l[-6:-1])) if len(l) >= 6 else l[-1]
    atr_extension = atr_multiplier * current_atr

    if signal.trend == 1:
        # Bullish: pullback = price retracing toward ST support
        distance_from_recent_low = current_close - float(np.min(l[-5:]))
        is_pullback = distance_from_recent_low < current_atr * 1.2
        is_continuation = current_close > prev_5_high + atr_extension * 0.3

        if is_pullback:
            return ExecTimingResult(
                mode=ExecMode.PULLBACK,
                confidence=round(min(1.0, 1.0 - distance_from_recent_low / (current_atr * 2)), 2),
                reason="Price near 15m low; pullback toward ST support",
            )
        if is_continuation:
            conf = min(1.0, (current_close - prev_5_high) / atr_extension)
            return ExecTimingResult(
                mode=ExecMode.CONTINUATION,
                confidence=round(conf, 2),
                reason="Bullish breakout above 5-bar range",
            )

    elif signal.trend == -1:
        distance_from_recent_high = float(np.max(h[-5:])) - current_close
        is_pullback = distance_from_recent_high < current_atr * 1.2
        is_continuation = current_close < prev_5_low - atr_extension * 0.3

        if is_pullback:
            return ExecTimingResult(
                mode=ExecMode.PULLBACK,
                confidence=round(min(1.0, 1.0 - distance_from_recent_high / (current_atr * 2)), 2),
                reason="Price near 15m high; pullback toward ST resistance",
            )
        if is_continuation:
            conf = min(1.0, (prev_5_low - current_close) / atr_extension)
            return ExecTimingResult(
                mode=ExecMode.CONTINUATION,
                confidence=round(conf, 2),
                reason="Bearish breakdown below 5-bar range",
            )

    return ExecTimingResult(
        mode=ExecMode.WAIT,
        confidence=0.0,
        reason="No clear pullback or continuation pattern on 15m",
    )
