import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import ExecTimingResult, ExecMode, SignalResult
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.ema import compute_ema
from app.engines.directional.microstructure import (
    detect_liquidity_sweep, detect_displacement,
)


def assess_timing(
    candles_15m: List[Candle],
    signal: SignalResult,
    atr_multiplier: float = 1.5,
    atr_pct: float = 0.0,
) -> ExecTimingResult:
    if len(candles_15m) < 20:
        return ExecTimingResult(
            mode=ExecMode.WAIT, confidence=0.0,
            reason="Insufficient 15m candles", exec_score=0.0,
        )

    h = np.array([c.high for c in candles_15m], dtype=np.float64)
    l = np.array([c.low for c in candles_15m], dtype=np.float64)
    c = np.array([c.close for c in candles_15m], dtype=np.float64)
    o = np.array([c.open for c in candles_15m], dtype=np.float64)
    volume = np.array([candle.volume for candle in candles_15m], dtype=np.float64)

    atr = compute_atr(h, l, c, 14)
    ema20 = compute_ema(c, 20)
    current_close = c[-1]
    current_open = o[-1]
    current_atr = atr[-1]
    current_ema20 = float(ema20[-1]) if ema20[-1] != 0.0 else current_close

    st_73_level = signal.st_values[0] if signal.st_values and signal.st_values[0] > 0 else 0.0
    prev_5_high = float(np.max(h[-6:-1])) if len(h) >= 6 else float(h[-1])
    prev_5_low = float(np.min(l[-6:-1])) if len(l) >= 6 else float(l[-1])
    atr_extension = atr_multiplier * current_atr

    vol_median = float(np.median(volume[-20:])) if len(volume) >= 20 else float(np.median(volume))

    # ── B1/B2: microstructure detectors ────────────────────────────────────
    # Direction inferred from signal.trend; sweep + displacement give additive
    # exec_score bumps on top of pullback (14) or continuation (10).
    direction = "long" if signal.trend == 1 else ("short" if signal.trend == -1 else "")
    sweep_hit, sweep_bonus, sweep_reason = (False, 0.0, "")
    disp_hit,  disp_bonus,  disp_reason  = (False, 0.0, "")
    if direction:
        sweep_hit, sweep_bonus, sweep_reason = detect_liquidity_sweep(
            h, l, c, o, direction,
        )
        disp_hit, disp_bonus, disp_reason = detect_displacement(
            h, l, c, o, atr=float(current_atr), direction=direction,
        )
    micro_bonus = round(sweep_bonus + disp_bonus, 2)
    micro_reason_parts = [r for r in (sweep_reason, disp_reason) if r]

    def _lower_wick_ratio() -> float:
        body = abs(current_close - current_open)
        if body < 1e-9:
            return 0.0
        lower_wick = (current_open - l[-1]) if current_close >= current_open else (current_close - l[-1])
        return lower_wick / body

    def _upper_wick_ratio() -> float:
        body = abs(current_close - current_open)
        if body < 1e-9:
            return 0.0
        upper_wick = (h[-1] - current_open) if current_close <= current_open else (h[-1] - current_close)
        return upper_wick / body

    if signal.trend == 1:
        # ── Mode A: PULLBACK to ST support + EMA20 confirmation ──────────
        if st_73_level > 0:
            distance_above_st = current_close - st_73_level
            ema20_ok = current_close > current_ema20
            if 0 <= distance_above_st < current_atr * 1.5 and ema20_ok:
                wick_bonus = 0.05 if _lower_wick_ratio() > 1.2 else 0.0
                conf = min(1.0, round(
                    max(0.0, 1.0 - distance_above_st / (current_atr * 1.5)) + wick_bonus, 2,
                ))
                reason = f"Pullback to ST(7,3) support {st_73_level:.0f}; EMA20 aligned"
                if micro_reason_parts:
                    reason += " | " + " + ".join(micro_reason_parts)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK, confidence=conf,
                    reason=reason,
                    exec_score=round(14.0 + micro_bonus, 2),
                )
        else:
            dist_from_low = current_close - float(np.min(l[-5:]))
            if dist_from_low < current_atr * 1.2 and current_close > current_ema20:
                conf = round(min(1.0, 1.0 - dist_from_low / (current_atr * 2)), 2)
                reason = "Price near 15m low; pullback toward ST support"
                if micro_reason_parts:
                    reason += " | " + " + ".join(micro_reason_parts)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK, confidence=conf,
                    reason=reason,
                    exec_score=round(14.0 + micro_bonus, 2),
                )

        # ── Mode B: CONTINUATION breakout + 2x volume ────────────────────
        if current_close > prev_5_high + atr_extension * 0.3 and volume[-1] > 2.0 * vol_median:
            conf = round(min(1.0, (current_close - prev_5_high) / atr_extension), 2)
            reason = "Bullish breakout above 5-bar range with 2x volume"
            if micro_reason_parts:
                reason += " | " + " + ".join(micro_reason_parts)
            return ExecTimingResult(
                mode=ExecMode.CONTINUATION, confidence=conf,
                reason=reason,
                exec_score=round(10.0 + micro_bonus, 2),
            )

    elif signal.trend == -1:
        # ── Mode A: PULLBACK to ST resistance + EMA20 confirmation ───────
        if st_73_level > 0:
            distance_below_st = st_73_level - current_close
            ema20_ok = current_close < current_ema20
            if 0 <= distance_below_st < current_atr * 1.5 and ema20_ok:
                wick_bonus = 0.05 if _upper_wick_ratio() > 1.2 else 0.0
                conf = min(1.0, round(
                    max(0.0, 1.0 - distance_below_st / (current_atr * 1.5)) + wick_bonus, 2,
                ))
                reason = f"Pullback to ST(7,3) resistance {st_73_level:.0f}; EMA20 aligned"
                if micro_reason_parts:
                    reason += " | " + " + ".join(micro_reason_parts)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK, confidence=conf,
                    reason=reason,
                    exec_score=round(14.0 + micro_bonus, 2),
                )
        else:
            dist_from_high = float(np.max(h[-5:])) - current_close
            if dist_from_high < current_atr * 1.2 and current_close < current_ema20:
                conf = round(min(1.0, 1.0 - dist_from_high / (current_atr * 2)), 2)
                reason = "Price near 15m high; pullback toward ST resistance"
                if micro_reason_parts:
                    reason += " | " + " + ".join(micro_reason_parts)
                return ExecTimingResult(
                    mode=ExecMode.PULLBACK, confidence=conf,
                    reason=reason,
                    exec_score=round(14.0 + micro_bonus, 2),
                )

        # ── Mode B: CONTINUATION breakdown + 2x volume ───────────────────
        if current_close < prev_5_low - atr_extension * 0.3 and volume[-1] > 2.0 * vol_median:
            conf = round(min(1.0, (prev_5_low - current_close) / atr_extension), 2)
            reason = "Bearish breakdown below 5-bar range with 2x volume"
            if micro_reason_parts:
                reason += " | " + " + ".join(micro_reason_parts)
            return ExecTimingResult(
                mode=ExecMode.CONTINUATION, confidence=conf,
                reason=reason,
                exec_score=round(10.0 + micro_bonus, 2),
            )

    return ExecTimingResult(
        mode=ExecMode.WAIT, confidence=0.0,
        reason="No clear pullback or continuation pattern on 15m",
        exec_score=0.0,
    )
