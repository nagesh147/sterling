"""Strategy 5: Breakout Momentum.

Looks for a clean breakout beyond a 4H key level combined with strong momentum.
Momentum is verified via RSI and candle characteristics.

  Bullish (Breakout of 4H resistance): Close > Resistance + tolerance, RSI > 60
  Bearish (Breakout of 4H support): Close < Support - tolerance, RSI < 40
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from app.engines.sterling_engine.config import ScalpingProfile as ScalpingConfig
from app.engines.sterling_engine.levels import Level, price_near_level
from app.engines.sterling_engine.risk import resolve_trade_risk


def current_atr(closes: NDArray[np.float64], highs: NDArray[np.float64], lows: NDArray[np.float64], period: int = 14) -> float:
    if len(closes) < period + 1:
        return float(np.mean(highs[-period:] - lows[-period:])) if len(closes) > 0 else 0.0
    tr = np.maximum(
        highs[-period:] - lows[-period:],
        np.maximum(
            np.abs(highs[-period:] - closes[-period-1:-1]),
            np.abs(lows[-period:] - closes[-period-1:-1])
        )
    )
    return float(np.mean(tr))


def calculate_rsi(closes: NDArray[np.float64], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-period-1:])
    gains = deltas[deltas > 0]
    losses = -deltas[deltas < 0]
    avg_gain = np.mean(gains) if len(gains) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_atr_series(closes: NDArray[np.float64], highs: NDArray[np.float64], lows: NDArray[np.float64], period: int = 14) -> NDArray[np.float64]:
    n = len(closes)
    atr = np.zeros(n, dtype=np.float64)
    tr = np.zeros(n, dtype=np.float64)
    
    if n > 0:
        tr[0] = highs[0] - lows[0]
        atr[0] = tr[0]
        
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        tr[i] = max(hl, hc, lc)
    
    for i in range(1, n):
        start_idx = max(0, i - period + 1)
        atr[i] = np.mean(tr[start_idx:i+1])
        
    return atr


@dataclass
class BreakoutSignal:
    underlying: str
    direction: str          # "long" | "short" | "none"
    pattern: str            # "bullish_breakout" | "bearish_breakout"
    near_level: Optional[float]
    level_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str
    entry_ok: bool
    timestamp_ms: int
    tp_source: str = ""
    rsi_value: float = 0.0


def evaluate_breakout(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list[Level],
    cfg: ScalpingConfig,
) -> BreakoutSignal:
    """Evaluate Strategy 5: Breakout Momentum."""
    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    if len(candles_15m) < 30 or len(candles_4h) < 20:
        return BreakoutSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="insufficient data", entry_ok=False, timestamp_ms=now_ms,
        )

    if not getattr(cfg, "enable_breakout", False):
        return BreakoutSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="strategy disabled", entry_ok=False, timestamp_ms=now_ms,
        )

    # Breakouts happen *through* levels. Find nearest level.
    nearby = price_near_level(current_price, levels, tolerance_pct=cfg.level_tolerance_pct * 4)
    if nearby is None:
        return BreakoutSignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="no nearby 4H level", entry_ok=False, timestamp_ms=now_ms,
        )

    closes = np.array([c.close for c in candles_15m], dtype=np.float64)
    lows_15m = np.array([c.low for c in candles_15m], dtype=np.float64)
    highs_15m = np.array([c.high for c in candles_15m], dtype=np.float64)
    volumes = np.array([c.volume for c in candles_15m], dtype=np.float64)

    rsi = calculate_rsi(closes)
    atr_val = current_atr(closes, highs_15m, lows_15m)

    level_price = nearby.price
    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False
    tp_source = ""

    is_ultra = getattr(cfg, "use_optimized", False)

    if is_ultra:
        # --- Ultra Breakout Momentum (Volatility-Based) ---
        atr_series = calculate_atr_series(closes, highs_15m, lows_15m, period=14)
        if len(atr_series) >= 20:
            atr_sma20 = np.mean(atr_series[-20:])
            current_atr_val = atr_series[-1]
            is_squeeze = current_atr_val < atr_sma20
        else:
            is_squeeze = False
            
        if len(closes) >= 50:
            recent_highs = highs_15m[-50:-1]
            recent_lows = lows_15m[-50:-1]
            channel_high = np.max(recent_highs)
            channel_low = np.min(recent_lows)
            
            vol_sma20 = np.mean(volumes[-20:-1]) if len(volumes) >= 20 else 0
            current_vol = volumes[-1]
            vol_spike = current_vol > (vol_sma20 * 2.5)
            
            bullish_breakout = current_price > channel_high and vol_spike
            bearish_breakout = current_price < channel_low and vol_spike
        else:
            bullish_breakout = False
            bearish_breakout = False
            channel_high = 0
            channel_low = 0

        if nearby.level_type == "resistance" and cfg.allow_long:
            if bullish_breakout and is_squeeze:
                entry = round(current_price, 4)
                stop_dist = 2.0 * max(atr_val, entry * 0.001)
                tp_dist = 4.0 * max(atr_val, entry * 0.001)
                
                stop_loss = round(entry - stop_dist, 4)
                take_profit = round(entry + tp_dist, 4)
                tp_source = "fixed_atr_bracket"
                direction = "long"
                pattern = "ultra_bullish_breakout"
                entry_ok = True
                reason = f"Ultra Breakout: vol spike above channel {channel_high:.0f} near 4H {level_price:.0f} · Fixed ATR Bracket"
            else:
                reason = f"Watching Ultra: Squeeze={is_squeeze}, vol_spike={vol_spike} near 4H {level_price:.0f}"
                
        elif nearby.level_type == "support" and cfg.allow_short:
            if bearish_breakout and is_squeeze:
                entry = round(current_price, 4)
                stop_dist = 2.0 * max(atr_val, entry * 0.001)
                tp_dist = 4.0 * max(atr_val, entry * 0.001)
                
                stop_loss = round(entry + stop_dist, 4)
                take_profit = round(entry - tp_dist, 4)
                tp_source = "fixed_atr_bracket"
                direction = "short"
                pattern = "ultra_bearish_breakout"
                entry_ok = True
                reason = f"Ultra Breakout: vol spike below channel {channel_low:.0f} near 4H {level_price:.0f} · Fixed ATR Bracket"
            else:
                reason = f"Watching Ultra: Squeeze={is_squeeze}, vol_spike={vol_spike} near 4H {level_price:.0f}"

    else:
        # --- Retest-entry Breakout (rebuilt 2026-06-01) ---
        # Instead of CHASING the breakout candle (entry at the high, stop at the
        # just-broken level → reverts and stops out), wait for the break, then
        # for price to PULL BACK and retest the broken level, and enter on the
        # hold with a tight stop just beyond the level.
        tolerance = level_price * (cfg.level_tolerance_pct / 100.0)
        band = level_price * (getattr(cfg, "bo_retest_band_pct", 0.4) / 100.0)
        lookback = int(getattr(cfg, "bo_retest_lookback", 12))
        cur = candles_15m[-1]
        prior_highs = highs_15m[-lookback - 1:-1] if len(highs_15m) > lookback else highs_15m[:-1]
        prior_lows = lows_15m[-lookback - 1:-1] if len(lows_15m) > lookback else lows_15m[:-1]

        if nearby.level_type == "resistance" and cfg.allow_long:
            # 1. price broke ABOVE the level on a recent (prior) bar
            broke_above = bool(prior_highs.size and np.any(prior_highs > level_price + tolerance))
            # 2. price has pulled back into the retest band just above the level
            retesting = level_price <= current_price <= level_price + band
            # 3. this bar dipped to test the level (without falling through) and closed up
            held = (cur.close >= cur.open
                    and cur.low <= level_price + band
                    and cur.low >= level_price - tolerance)
            if broke_above and retesting and held:
                entry = round(current_price, 4)
                # Tight stop just BELOW the retested level (now support), ATR cushion.
                cushion = 0.25 * atr_val if atr_val > 0 else level_price * 0.001
                sl = level_price - cushion
                risk = entry - sl
                if risk > 0 and (atr_val <= 0 or risk <= cfg.max_stop_atr * atr_val):
                    stop_loss = round(sl, 4)
                    take_profit = round(entry + max(cfg.min_rr, 2.0) * risk, 4)
                    direction = "long"; pattern = "breakout_retest_long"
                    tp_source = "retest_atr_bracket"; entry_ok = True
                    reason = (f"Retest of broken 4H resistance {level_price:.0f} held — long · "
                              f"R:R {(take_profit - entry) / risk:.1f}")
                else:
                    reason = f"retest of 4H resistance {level_price:.0f} — stop too wide, skip"
            elif broke_above and not retesting:
                reason = f"Watching: broke 4H resistance {level_price:.0f} — awaiting pullback to retest (price {current_price:.0f})"
            elif broke_above:
                reason = f"Watching: retesting 4H resistance {level_price:.0f} — awaiting a bullish hold"
            else:
                reason = f"Watching: near 4H resistance {level_price:.0f} — no breakout yet"

        elif nearby.level_type == "support" and cfg.allow_short:
            broke_below = bool(prior_lows.size and np.any(prior_lows < level_price - tolerance))
            retesting = level_price - band <= current_price <= level_price
            held = (cur.close <= cur.open
                    and cur.high >= level_price - band
                    and cur.high <= level_price + tolerance)
            if broke_below and retesting and held:
                entry = round(current_price, 4)
                # Tight stop just ABOVE the retested level (now resistance), ATR cushion.
                cushion = 0.25 * atr_val if atr_val > 0 else level_price * 0.001
                sl = level_price + cushion
                risk = sl - entry
                if risk > 0 and (atr_val <= 0 or risk <= cfg.max_stop_atr * atr_val):
                    stop_loss = round(sl, 4)
                    take_profit = round(entry - max(cfg.min_rr, 2.0) * risk, 4)
                    direction = "short"; pattern = "breakout_retest_short"
                    tp_source = "retest_atr_bracket"; entry_ok = True
                    reason = (f"Retest of broken 4H support {level_price:.0f} held — short · "
                              f"R:R {(entry - take_profit) / risk:.1f}")
                else:
                    reason = f"retest of 4H support {level_price:.0f} — stop too wide, skip"
            elif broke_below and not retesting:
                reason = f"Watching: broke 4H support {level_price:.0f} — awaiting pullback to retest (price {current_price:.0f})"
            elif broke_below:
                reason = f"Watching: retesting 4H support {level_price:.0f} — awaiting a bearish hold"
            else:
                reason = f"Watching: near 4H support {level_price:.0f} — no breakdown yet"

    if not pattern and "Watching" not in reason and "skipped" not in reason:
        reason = f"near 4H {nearby.level_type} @ {level_price:.0f} — RSI: {rsi:.1f}"

    return BreakoutSignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source,
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
        rsi_value=round(float(rsi), 2),
    )
