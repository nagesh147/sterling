"""
A6: Dynamic take-profit selection.

Replaces a static R-multiple TP with the closer of two anchors:
  • r_target  = entry ± (stop_dist × rr)
  • swing     = recent swing high/low ± 1.5 ATR

For longs we take min(r_target, swing) — the more achievable target,
i.e. higher hit-rate. For shorts the analogous max(r_target, swing).

Pure function: takes precomputed series; no dependencies on adapters or
schemas, so it's trivial to unit-test on synthetic candles.
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
    """
    Returns (tp_price, source) where source ∈ {"r_target", "swing", "fallback"}.

    direction: "long" | "short" (case-insensitive); anything else → r_target only.
    swing_lookback: bars (typically 20× 4H = ~3 days) used to find recent extreme.
    atr_mult: how far past the swing to extend the projection.
    """
    if entry <= 0 or stop_dist <= 0 or rr <= 0:
        # Defensive: caller should guard, but never crash a live signal.
        return (round(entry, 2), "fallback")

    d = direction.lower()
    r_target = entry + stop_dist * rr if d == "long" else entry - stop_dist * rr

    if highs is None or lows is None or len(highs) == 0 or len(lows) == 0 or atr <= 0:
        return (round(r_target, 2), "r_target")

    n = min(swing_lookback, len(highs), len(lows))
    if d == "long":
        swing_high = float(np.max(highs[-n:]))
        swing_target = swing_high + atr_mult * atr
        # min = closer to entry from above = more achievable
        if swing_target < r_target:
            return (round(swing_target, 2), "swing")
        return (round(r_target, 2), "r_target")

    if d == "short":
        swing_low = float(np.min(lows[-n:]))
        swing_target = swing_low - atr_mult * atr
        # max = closer to entry from below = more achievable
        if swing_target > r_target:
            return (round(swing_target, 2), "swing")
        return (round(r_target, 2), "r_target")

    return (round(r_target, 2), "r_target")


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
    """
    B3: Re-evaluate TP on each monitor tick. Returns (new_tp, changed, source).

    Guards:
      • new_tp must remain a winning target relative to entry (no moving the
        goalpost behind us).
      • new_tp must remain on the correct side of current_spot, otherwise it
        would trigger an immediate TP exit.
      • Only adopt new_tp if it differs from current_tp by ≥ min_change_pct%
        to avoid thrashing on micro-fluctuations.
    """
    if entry <= 0 or current_tp <= 0:
        return (current_tp, False, "no_change")

    cand_tp, src = dynamic_tp(
        direction, entry, stop_dist, rr, highs, lows, atr,
        swing_lookback=swing_lookback,
    )
    d = direction.lower()

    # Guard: must keep TP on the favorable side of entry
    if d == "long" and cand_tp <= entry:
        return (current_tp, False, "guard_entry")
    if d == "short" and cand_tp >= entry:
        return (current_tp, False, "guard_entry")

    # Guard: must keep TP on the not-yet-hit side of current spot
    if current_spot > 0:
        if d == "long" and cand_tp <= current_spot:
            return (current_tp, False, "guard_spot")
        if d == "short" and cand_tp >= current_spot:
            return (current_tp, False, "guard_spot")

    pct_change = abs(cand_tp - current_tp) / max(current_tp, 1e-6) * 100.0
    if pct_change < min_change_pct:
        return (current_tp, False, "below_threshold")

    return (round(cand_tp, 2), True, src)
