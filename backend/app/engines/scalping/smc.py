"""Strategy 2: Smart Money Concepts (SMC) scalping.

After a 4H liquidity zone test:
  Bullish: inducement (false breakdown) then bullish imbalance candle
             (large bullish body engulfing prior bearish candle's range)
  Bearish: inducement (false breakout) then bearish imbalance candle
             (large bearish body engulfing prior bullish candle's range)

Entry  = immediately after imbalance candle close
Stop   = below imbalance candle low (long) / above high (short)
Target = nearest 15min resistance (long) / support (short)

Relaxed detection: we scan the last N bars for the pattern sequence
(SMC valid candle near a level), not just one candle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import numpy as np
from numpy.typing import NDArray

from app.engines.scalping.config import ScalpingProfile as ScalpingConfig
from app.engines.scalping.levels import Level, price_near_level, nearest_level, detect_levels
from app.engines.scalping.risk import atr, resolve_trade_risk


@dataclass
class SMCESignal:
    underlying: str
    direction: str          # "long" | "short" | "none"
    pattern: str            # "bullish_imbalance" | "bearish_imbalance" | ""
    near_level: Optional[float]
    level_type: str
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str
    entry_ok: bool
    timestamp_ms: int
    tp_source: str = ""


def evaluate_bullish_smc(
    opens: NDArray,
    highs: NDArray,
    lows: NDArray,
    closes: NDArray,
    level_price: float,
    cfg: ScalpingConfig
) -> Optional[Dict[str, Any]]:
    """
    Validates immediate Inducement + Imbalance structure at a 4H Support Level.
    """
    n = len(closes) - 1 # Index of the most recently completed candle
    
    current_open = float(opens[n])
    current_close = float(closes[n])
    current_high = float(highs[n])
    current_low = float(lows[n])
    
    # 1. Displacement/Imbalance Check: Current candle must be aggressively bullish
    if current_close <= current_open:
        return None

    prev_open = float(opens[n - 1]); prev_close = float(closes[n - 1])
    prev_high = float(highs[n - 1]); prev_low = float(lows[n - 1])

    # Doc: the bullish imbalance candle must completely engulf the range of the
    # PREVIOUS BEARISH candle WITH ITS BODY — i.e. open at/below the prior low and
    # close at/above the prior high. (Prior candle must itself be bearish.)
    if prev_close >= prev_open:
        return None
    if not (current_open <= prev_low and current_close >= prev_high):
        return None

    # 2. Time-Constrained Sweep Check
    # Scan only the immediate 1 to 3 bars prior to the imbalance candle
    inducement_found = False
    sweep_low = current_low
    scan_start = max(0, n - cfg.smc_max_sweep_window)
    
    for j in range(scan_start, n):
        # Inducement Condition: Price wicks beneath the 4H support zone but closes above it
        if float(lows[j]) < level_price and float(closes[j]) > level_price:
            inducement_found = True
            sweep_low = min(sweep_low, float(lows[j]))
            break
            
    if inducement_found:
        return {
            "pattern": "smc_inducement_imbalance",
            "direction": "long",
            "entry": round(current_close, 4),
            "stop_loss": round(sweep_low * 0.999, 4), # Protected beneath the sweep wick low
        }
        
    return None


def evaluate_bearish_smc(
    opens: NDArray,
    highs: NDArray,
    lows: NDArray,
    closes: NDArray,
    level_price: float,
    cfg: ScalpingConfig
) -> Optional[Dict[str, Any]]:
    """
    Validates immediate Inducement + Imbalance structure at a 4H Resistance Level.
    """
    n = len(closes) - 1
    
    current_open = float(opens[n])
    current_close = float(closes[n])
    current_high = float(highs[n])
    current_low = float(lows[n])
    
    if current_close >= current_open:
        return None

    prev_open = float(opens[n - 1]); prev_close = float(closes[n - 1])
    prev_high = float(highs[n - 1]); prev_low = float(lows[n - 1])

    # Doc: the bearish imbalance candle must completely engulf the range of the
    # PREVIOUS BULLISH candle WITH ITS BODY — open at/above the prior high and
    # close at/below the prior low. (Prior candle must itself be bullish.)
    if prev_close <= prev_open:
        return None
    if not (current_open >= prev_high and current_close <= prev_low):
        return None

    inducement_found = False
    sweep_high = current_high
    scan_start = max(0, n - cfg.smc_max_sweep_window)
    
    for j in range(scan_start, n):
        if float(highs[j]) > level_price and float(closes[j]) < level_price:
            inducement_found = True
            sweep_high = max(sweep_high, float(highs[j]))
            break
            
    if inducement_found:
        return {
            "pattern": "smc_inducement_imbalance",
            "direction": "short",
            "entry": round(current_close, 4),
            "stop_loss": round(sweep_high * 1.001, 4),
        }
        
    return None


def evaluate_smc(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    levels: list[Level],
    cfg: ScalpingConfig,
) -> SMCESignal:
    """Evaluate Strategy 2: SMC inducement + imbalance."""
    now_ms = int(candles_15m[-1].timestamp_ms) if candles_15m else 0
    current_price = float(candles_15m[-1].close) if candles_15m else 0.0

    if len(candles_15m) < 20 or len(candles_4h) < 20:
        return SMCESignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="insufficient data", entry_ok=False, timestamp_ms=now_ms,
        )

    if not cfg.enable_smc:
        return SMCESignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="strategy disabled", entry_ok=False, timestamp_ms=now_ms,
        )

    nearby = price_near_level(current_price, levels, tolerance_pct=cfg.level_tolerance_pct * 3)
    if nearby is None:
        return SMCESignal(
            underlying=underlying, direction="none", pattern="",
            near_level=None, level_type="",
            entry=None, stop_loss=None, take_profit=None,
            reason="no nearby 4H liquidity zone", entry_ok=False, timestamp_ms=now_ms,
        )

    highs = np.array([c.high for c in candles_15m], dtype=np.float64)
    lows = np.array([c.low for c in candles_15m], dtype=np.float64)
    opens = np.array([c.open for c in candles_15m], dtype=np.float64)
    closes = np.array([c.close for c in candles_15m], dtype=np.float64)
    ts15 = np.array([c.timestamp_ms for c in candles_15m], dtype=np.int64)
    level_price = nearby.price
    # Doc: SMC target is the closest *15-minute* key level (not the 4H zone).
    levels_15m = detect_levels(highs, lows, closes, ts15, cfg)

    direction = "none"
    pattern = ""
    entry = None
    stop_loss = None
    take_profit = None
    reason = ""
    entry_ok = False

    atr_val = atr(highs, lows, closes)

    # Ultra Mode: 4H Macro-Fenced Scalper (Z-Score +/- 2.5)
    z_score = 0.0
    if getattr(cfg, "use_optimized", False):
        closes_4h = np.array([c.close for c in candles_4h], dtype=np.float64)
        if len(closes_4h) >= 20:
            recent_closes = closes_4h[-20:]
            mean_4h = np.mean(recent_closes)
            std_4h = np.std(recent_closes)
            if std_4h != 0:
                z_score = (current_price - mean_4h) / std_4h
                
    macro_bullish = z_score <= -2.5 if getattr(cfg, "use_optimized", False) else True
    macro_bearish = z_score >= 2.5 if getattr(cfg, "use_optimized", False) else True

    if nearby.level_type == "support" and cfg.allow_long:
        if not macro_bullish:
            reason = f"Watching: near 4H support @ {level_price:.0f} — skipped (4H Z-Score {z_score:.2f} > -2.5)"
        else:
            result = evaluate_bullish_smc(opens, highs, lows, closes, level_price, cfg)
            if result is not None:
                pattern = result["pattern"]
                entry = result["entry"]
                plan = resolve_trade_risk(
                    direction="long", entry=entry, structure_stop=float(result["stop_loss"]),
                    atr_val=atr_val, levels=levels_15m, tp_level_type="resistance",
                    min_rr=cfg.min_rr, max_stop_atr=cfg.max_stop_atr,
                )
                if plan.ok:
                    direction = "long"
                    stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                    entry_ok = True
                    reason = f"bullish imbalance engulfing prior bearish candle after inducement below 4H support {level_price:.0f} (Z: {z_score:.2f}) · R:R {plan.rr}"
                else:
                    pattern = "smc_inducement_imbalance"; entry = None
                    reason = f"bullish imbalance near 4H support {level_price:.0f} — skipped: {plan.reason}"

    elif nearby.level_type == "resistance" and cfg.allow_short:
        if not macro_bearish:
            reason = f"Watching: near 4H resistance @ {level_price:.0f} — skipped (4H Z-Score {z_score:.2f} < 2.5)"
        else:
            result = evaluate_bearish_smc(opens, highs, lows, closes, level_price, cfg)
            if result is not None:
                pattern = result["pattern"]
                entry = result["entry"]
                plan = resolve_trade_risk(
                    direction="short", entry=entry, structure_stop=float(result["stop_loss"]),
                    atr_val=atr_val, levels=levels_15m, tp_level_type="support",
                    min_rr=cfg.min_rr, max_stop_atr=cfg.max_stop_atr,
                )
                if plan.ok:
                    direction = "short"
                    stop_loss, take_profit, tp_source = plan.stop_loss, plan.take_profit, plan.tp_source
                    entry_ok = True
                    reason = f"bearish imbalance engulfing prior bullish candle after inducement above 4H resistance {level_price:.0f} (Z: {z_score:.2f}) · R:R {plan.rr}"
                else:
                    pattern = "smc_inducement_imbalance"; entry = None
                    reason = f"bearish imbalance near 4H resistance {level_price:.0f} — skipped: {plan.reason}"

    if not pattern and "skipped" not in reason:
        # Provide context even when no pattern is found
        if nearby.level_type == "support":
            reason = f"Watching: near 4H support @ {level_price:.0f} — awaiting inducement + imbalance"
        else:
            reason = f"Watching: near 4H resistance @ {level_price:.0f} — awaiting inducement + imbalance"

    return SMCESignal(
        underlying=underlying, direction=direction, pattern=pattern,
        near_level=round(level_price, 4), level_type=nearby.level_type,
        entry=entry, stop_loss=stop_loss, take_profit=take_profit, tp_source=tp_source if 'tp_source' in locals() else "",
        reason=reason, entry_ok=entry_ok, timestamp_ms=now_ms,
    )