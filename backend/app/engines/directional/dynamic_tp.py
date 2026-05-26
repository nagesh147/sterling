"""STRATEGY STUB — dynamic take-profit logic removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. These helpers retain their
signatures so callers keep working. `dynamic_tp` falls back to a plain
risk-reward target (entry ± rr × stop_dist); `recompute_tp` never moves the TP.

Implement the new dynamic-TP logic here.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def dynamic_tp(
    direction: str,
    entry: float,
    stop_dist: float,
    rr: float,
    highs: np.ndarray,
    lows: np.ndarray,
    atr: float,
    swing_lookback: int = 20,
    atr_mult: float = 1.5,
    tp_level: float | None = None,
) -> Tuple[float, str]:
    """
    Computes a dynamic take profit based on provided structural levels or recent swings,
    falling back to a fixed RR target if structural logic cannot find a valid level.
    """
    is_long = str(direction).lower() in ("long", "bullish", "buy")
    
    # 1. Base RR Target (Fallback safety net)
    rr_target = entry + (rr * stop_dist) if is_long else entry - (rr * stop_dist)
    
    # 2. Hard Structural Level (e.g. 4H resistance/support passed from scalping engine)
    if tp_level is not None:
        return float(round(tp_level, 4)), "structural_level"
    
    # 3. Dynamic Swing Target
    try:
        if len(highs) >= swing_lookback and len(lows) >= swing_lookback:
            if is_long:
                # Look for recent resistance (swing high)
                recent_highs = highs[-swing_lookback:]
                structural_target = float(np.max(recent_highs))
                # Target must provide at least 1R to be worth it
                min_target = entry + stop_dist
                if structural_target >= min_target:
                    # Pad it slightly with ATR
                    final_target = structural_target - (atr * atr_mult * 0.2)
                    return float(round(final_target, 4)), "swing_high_target"
            else:
                # Look for recent support (swing low)
                recent_lows = lows[-swing_lookback:]
                structural_target = float(np.min(recent_lows))
                min_target = entry - stop_dist
                if structural_target <= min_target:
                    # Pad it slightly with ATR
                    final_target = structural_target + (atr * atr_mult * 0.2)
                    return float(round(final_target, 4)), "swing_low_target"
    except Exception:
        pass
        
    return float(round(rr_target, 4)), "fallback_rr_target"



def recompute_tp(
    direction: str,
    entry: float,
    current_tp: float,
    current_spot: float,
    stop_dist: float,
    rr: float,
    highs: np.ndarray,
    lows: np.ndarray,
    atr: float,
    min_change_pct: float = 1.0,
    swing_lookback: int = 30,
) -> Tuple[float, bool, str]:
    """Neutral: never move the TP (no strategy loaded)."""
    return float(current_tp), False, "stub_no_change"
