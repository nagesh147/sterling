"""Shared risk resolution for the scalping strategies.

This module exists because the per-strategy SL/TP logic had three structural
defects that a volatile market exploits:

  • Risk asymmetry — `dynamic_tp` short-circuits to the *nearest* structural
    level and ignores the stop distance, so a wide structural stop gets paired
    with a tiny nearest-level target (observed live: R:R ≈ 0.16). Systematic
    bleed: tiny wins, huge losses.
  • Stop-hunt exposure — stops placed exactly on the obvious pattern low / zone
    edge get swept before the move continues.
  • Un-scalpable risk — a structurally-valid but very wide stop (deep pattern,
    far zone) produces a trade no scalper should take.

`resolve_trade_risk` fixes all three:
  1. Dynamic ATR stop: structural level + an ATR cushion (so the stop sits past
     the obvious level), floored so noise can't hit a too-tight stop.
  2. Hard reject if the resulting risk is wider than `max_stop_atr`×ATR or
     `max_risk_pct` of price — un-scalpable setups never arm.
  3. R:R gate: the target must be a structural level that is at least `min_rr`×
     risk away. If the *natural* (nearest) level is too close, the setup is
     rejected rather than armed with a doomed reward:risk.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray


def atr(highs: NDArray, lows: NDArray, closes: NDArray, period: int = 14) -> float:
    """Average True Range over the last `period` bars (simple mean of TR)."""
    n = len(closes)
    if n < 2:
        return 0.0
    p = min(period, n - 1)
    tr = np.maximum(
        highs[-p:] - lows[-p:],
        np.maximum(
            np.abs(highs[-p:] - closes[-p - 1:-1]),
            np.abs(lows[-p:] - closes[-p - 1:-1]),
        ),
    )
    return float(np.mean(tr)) if len(tr) else 0.0


@dataclass
class RiskPlan:
    ok: bool
    stop_loss: Optional[float]
    take_profit: Optional[float]
    tp_source: str
    rr: float
    risk_pct: float
    reason: str


def resolve_trade_risk(
    *,
    direction: str,                 # "long" | "short"
    entry: float,
    structure_stop: float,          # raw structural invalidation (pattern low/high, zone edge…)
    atr_val: float,
    levels,                         # List[Level] used to pick the target (15m for PA/SMC, 4H for MA)
    tp_level_type: str,             # "resistance" for longs, "support" for shorts
    min_rr: float = 1.5,
    atr_buffer_mult: float = 0.25,  # cushion beyond the structural stop (anti stop-hunt)
    min_stop_atr: float = 0.5,      # floor: stop never tighter than this × ATR
    max_stop_atr: float = 4.0,      # ceiling: reject if structural stop is wider than this × ATR
    max_risk_pct: float = 3.0,      # ceiling: reject if stop is wider than this % of price
) -> RiskPlan:
    """Turn a raw structural stop + a set of levels into an SL/TP that clears a
    minimum reward:risk, or reject the setup."""
    is_long = str(direction).lower() in ("long", "bullish", "buy")

    # ── 1. Dynamic stop: structural distance + ATR cushion, floored ──────────
    buffer = atr_buffer_mult * atr_val
    stop_dist = abs(entry - structure_stop) + buffer
    if atr_val > 0:
        stop_dist = max(stop_dist, min_stop_atr * atr_val)
    if stop_dist <= 0:
        stop_dist = entry * 0.005                       # last-resort 0.5% guard
    stop_loss = entry - stop_dist if is_long else entry + stop_dist

    risk_pct = stop_dist / entry * 100 if entry else 999.0

    # ── 2. Reject un-scalpable risk ──────────────────────────────────────────
    if risk_pct > max_risk_pct:
        return RiskPlan(False, None, None, "", 0.0, risk_pct,
                        f"stop {risk_pct:.2f}% > {max_risk_pct:.1f}% cap (un-scalpable)")
    if atr_val > 0 and stop_dist > max_stop_atr * atr_val:
        return RiskPlan(False, None, None, "", 0.0, risk_pct,
                        f"stop {stop_dist / max(atr_val,1e-9):.1f}×ATR > {max_stop_atr:.1f}×ATR (structure too far)")

    # ── 3. R:R-gated target ──────────────────────────────────────────────────
    min_reward = min_rr * stop_dist
    rr_target = entry + min_reward if is_long else entry - min_reward

    typed = [l for l in (levels or []) if l.level_type == tp_level_type]
    # Levels that sit at least min_rr away (in the trade's favour).
    if is_long:
        far_enough = [l.price for l in typed if l.price >= rr_target]
    else:
        far_enough = [l.price for l in typed if l.price <= rr_target]

    if far_enough:
        # Nearest worthwhile structural target (closest level still ≥ min_rr away).
        tp = min(far_enough) if is_long else max(far_enough)
        tp_source = "structural_level"
    elif typed:
        # Structural levels EXIST in the target direction but are all closer than
        # min_rr — the natural target is too close. A volatile stop against a
        # cramped target is exactly the asymmetry we refuse to take. Reject.
        return RiskPlan(False, None, None, "", 0.0, risk_pct,
                        f"nearest {tp_level_type} target < {min_rr:.1f}R away (cramped — skip)")
    else:
        # Open space (no structural level ahead): take the measured min-R:R target.
        tp = rr_target
        tp_source = "min_rr_target"

    rr = abs(tp - entry) / stop_dist if stop_dist else 0.0
    return RiskPlan(True, round(stop_loss, 4), round(tp, 4), tp_source, round(rr, 2), risk_pct, "ok")
