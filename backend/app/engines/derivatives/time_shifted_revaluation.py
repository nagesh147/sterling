"""Time-shifted BSM revaluation — the CORRECT theta gate.

Plan-agent's critique nailed this one: a separate "theta budget" double-
counts decay because theta is already implicit in the BSM-priced option
price at exit-T. The right model is to BSM-price the option at the
expected EXIT time and spot, and read the realised PnL ratio directly.

Inputs:
  • current spot, IV, DTE_now
  • target exit spot (entry ± rr·stop_dist) and stop spot
  • expected hold time (so DTE_at_exit = DTE_now − hold_days)

Output:
  • premium_now (entry premium given current market)
  • premium_at_tp (BSM at target spot + DTE_at_exit)
  • premium_at_sl (BSM at stop spot + DTE_at_exit)
  • expected_R = (premium_at_tp − premium_now) / (premium_now − premium_at_sl)
  • theta_burn = premium_now × (1 − (BSM-no-spot-move-at-exit-T)/premium_now)
  • veto_reason — "premium_floor_crushed" when premium_at_tp < 0.50 × premium_now
    (Plan agent's hard rule)

The selector rejects candidates with expected_R < min_rr OR veto_reason set.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.backtest.bs_pricing import bs_price


@dataclass
class RevaluationResult:
    premium_now: float
    premium_at_tp: float
    premium_at_sl: float
    premium_at_exit_no_move: float          # BSM at exit-T with spot unchanged
    expected_r: float
    theta_burn_pct: float                   # fraction of premium lost to pure decay
    veto_reason: str = ""                   # "" = pass


def revalue(
    *,
    spot_now: float,
    spot_tp: float,
    spot_sl: float,
    strike: float,
    dte_now: int,
    expected_hold_days: float,
    iv: float,
    is_call: bool,
    r: float = 0.0,
    premium_floor_pct: float = 0.50,        # Plan-agent rule: reject if TP premium < 50% of entry
) -> Optional[RevaluationResult]:
    """Reprice the option at expected exit time + target/stop spots.

    Returns None when inputs are degenerate (would-be premium ≤ 0).
    """
    if dte_now <= 0 or iv <= 0 or strike <= 0:
        return None

    dte_at_exit = max(0, dte_now - int(expected_hold_days))
    opt_type = "call" if is_call else "put"

    p_now = bs_price(spot_now, strike, dte_now, iv, opt_type, r) or 0.0
    if p_now <= 0:
        return None
    # Floor exit-time DTE at 1 so BSM still produces a positive premium
    # for very-short-hold scenarios — DTE=0 would zero everything out.
    dte_exit_for_bsm = max(1, dte_at_exit)
    p_tp = bs_price(spot_tp, strike, dte_exit_for_bsm, iv, opt_type, r) or 0.0
    p_sl = bs_price(spot_sl, strike, dte_exit_for_bsm, iv, opt_type, r) or 0.0
    p_no_move = bs_price(spot_now, strike, dte_exit_for_bsm, iv, opt_type, r) or 0.0

    veto = ""
    if p_tp < premium_floor_pct * p_now:
        veto = f"premium_floor_crushed:tp={p_tp:.2f}<{premium_floor_pct:.0%}×entry={p_now:.2f}"

    sl_drop = p_now - p_sl
    expected_r = (p_tp - p_now) / sl_drop if sl_drop > 0 else 0.0
    theta_burn = max(0.0, (p_now - p_no_move) / p_now) if p_now > 0 else 0.0

    return RevaluationResult(
        premium_now=p_now,
        premium_at_tp=p_tp,
        premium_at_sl=p_sl,
        premium_at_exit_no_move=p_no_move,
        expected_r=expected_r,
        theta_burn_pct=theta_burn,
        veto_reason=veto,
    )
