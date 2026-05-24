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
) -> Tuple[float, str]:
    """Fallback: plain RR target, no swing/ATR structure logic."""
    is_long = str(direction).lower() in ("long", "bullish", "buy")
    tp = entry + rr * stop_dist if is_long else entry - rr * stop_dist
    return float(tp), "stub_rr_target"


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
