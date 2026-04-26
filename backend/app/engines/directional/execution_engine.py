import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import ExecTimingResult, ExecMode, SignalResult
from app.engines.indicators.atr import compute_atr


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
    current_close = c[-1]
    current_atr = atr[-1]

    # 1H ST(7,3) level from signal (support for long, resistance for short)
    st_73_level = signal.st_values[0] if signal.st_values and signal.st_values[0] > 0 else 0.0

    # Continuation breakout parameters
    prev_5_high = float(np.max(h[-6:-1])) if len(h) >= 6 else float(h[-1])
    prev_5_low = float(np.min(l[-6:-1])) if len(l) >= 6 else float(l[-1])
    atr_extension = atr_multiplier * current_atr

    if signal.trend == 1:
        # Bullish: ST(7,3) is below price acting as support
        if st_73_level > 0:
            distance_above_st = current_close - st_73_level
            # Pullback: within 1.5 ATR of ST support AND still above it (hold confirmation)
            if 0 <= distance_above_st < current_atr * 1.5:
                conf = round(max(0.0, min(1.0, 1.0 - distance_above_st / (current_atr * 1.5))), 2)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK,
                    confidence=conf,
                    reason=f"Pullback to ST(7,3) support {st_73_level:.0f}; distance {distance_above_st:.0f}; hold confirmed",
                )
        else:
            # Fallback: price near recent 5-bar low
            distance_from_recent_low = current_close - float(np.min(l[-5:]))
            if distance_from_recent_low < current_atr * 1.2:
                conf = round(min(1.0, 1.0 - distance_from_recent_low / (current_atr * 2)), 2)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK,
                    confidence=conf,
                    reason="Price near 15m low; pullback toward ST support",
                )

        # Continuation: breakout above 5-bar range + ATR extension
        if current_close > prev_5_high + atr_extension * 0.3:
            conf = round(min(1.0, (current_close - prev_5_high) / atr_extension), 2)
            return ExecTimingResult(
                mode=ExecMode.CONTINUATION,
                confidence=conf,
                reason="Bullish breakout above 5-bar range",
            )

    elif signal.trend == -1:
        # Bearish: ST(7,3) is above price acting as resistance
        if st_73_level > 0:
            distance_below_st = st_73_level - current_close
            # Pullback: within 1.5 ATR of ST resistance AND still below it (hold confirmation)
            if 0 <= distance_below_st < current_atr * 1.5:
                conf = round(max(0.0, min(1.0, 1.0 - distance_below_st / (current_atr * 1.5))), 2)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK,
                    confidence=conf,
                    reason=f"Pullback to ST(7,3) resistance {st_73_level:.0f}; distance {distance_below_st:.0f}; hold confirmed",
                )
        else:
            # Fallback: price near recent 5-bar high
            distance_from_recent_high = float(np.max(h[-5:])) - current_close
            if distance_from_recent_high < current_atr * 1.2:
                conf = round(min(1.0, 1.0 - distance_from_recent_high / (current_atr * 2)), 2)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK,
                    confidence=conf,
                    reason="Price near 15m high; pullback toward ST resistance",
                )

        # Continuation: breakdown below 5-bar range
        if current_close < prev_5_low - atr_extension * 0.3:
            conf = round(min(1.0, (prev_5_low - current_close) / atr_extension), 2)
            return ExecTimingResult(
                mode=ExecMode.CONTINUATION,
                confidence=conf,
                reason="Bearish breakdown below 5-bar range",
            )

    return ExecTimingResult(
        mode=ExecMode.WAIT,
        confidence=0.0,
        reason="No clear pullback or continuation pattern on 15m",
    )
