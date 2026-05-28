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

from app.engines.scalping.config import ScalpingProfile as ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level
from app.engines.scalping.risk import resolve_trade_risk


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
        # --- Standard Breakout Momentum (RSI-Based) ---
        if nearby.level_type == "resistance" and cfg.allow_long:
            tolerance = level_price * (cfg.level_tolerance_pct / 100.0)
            is_breakout = current_price > (level_price + tolerance)
            
            if is_breakout and rsi >= getattr(cfg, "bo_rsi_long_threshold", 60.0):
                entry = round(current_price, 4)
                # Stop loss below the broken resistance level
                plan = resolve_trade_risk(
                    direction="long", entry=entry, structure_stop=level_price,
                    atr_val=atr_val, levels=levels, tp_level_type="resistance",
                    max_risk_pct=4.0, max_stop_atr=cfg.max_stop_atr, min_rr=cfg.min_rr,
                )
                if plan.ok:
                    direction = "long"; pattern = "bullish_breakout"
                    stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                    entry_ok = True
                    reason = f"Breakout above 4H resistance {level_price:.0f} with RSI {rsi:.1f} · R:R {plan.rr}"
                else:
                    reason = f"breakout above 4H resistance {level_price:.0f} — skipped: {plan.reason}"
            elif is_breakout:
                reason = f"Watching: Breakout above 4H resistance {level_price:.0f} — awaiting RSI >= {getattr(cfg, 'bo_rsi_long_threshold', 60.0)} (current: {rsi:.1f})"
            else:
                reason = f"Watching: Near 4H resistance {level_price:.0f} — awaiting breakout (current: {current_price:.0f}, RSI: {rsi:.1f})"
    
        # Bearish Breakout: Must break BELOW a support level
        elif nearby.level_type == "support" and cfg.allow_short:
            tolerance = level_price * (cfg.level_tolerance_pct / 100.0)
            is_breakout = current_price < (level_price - tolerance)
            
            if is_breakout and rsi <= getattr(cfg, "bo_rsi_short_threshold", 40.0):
                entry = round(current_price, 4)
                # Stop loss above the broken support level
                plan = resolve_trade_risk(
                    direction="short", entry=entry, structure_stop=level_price,
                    atr_val=atr_val, levels=levels, tp_level_type="support",
                    max_risk_pct=4.0, max_stop_atr=cfg.max_stop_atr, min_rr=cfg.min_rr,
                )
                if plan.ok:
                    direction = "short"; pattern = "bearish_breakout"
                    stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                    entry_ok = True
                    reason = f"Breakout below 4H support {level_price:.0f} with RSI {rsi:.1f} · R:R {plan.rr}"
                else:
                    reason = f"breakout below 4H support {level_price:.0f} — skipped: {plan.reason}"
            elif is_breakout:
                reason = f"Watching: Breakout below 4H support {level_price:.0f} — awaiting RSI <= {getattr(cfg, 'bo_rsi_short_threshold', 40.0)} (current: {rsi:.1f})"
            else:
                reason = f"Watching: Near 4H support {level_price:.0f} — awaiting breakout (current: {current_price:.0f}, RSI: {rsi:.1f})"

    if not pattern and "Watching" not in reason and "skipped" not in reason:
        reason = f"near 4H {nearby.level_type} @ {level_price:.0f} — RSI: {rsi:.1f}"

    return BreakoutSignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source,
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
        rsi_value=round(float(rsi), 2),
    )
