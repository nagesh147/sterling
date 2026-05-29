"""Black-Scholes Greeks for options positions + portfolio Greeks budget.

`bsm_greeks_full` is the canonical 5-Greek (delta/gamma/vega/theta/rho)
entry point and delegates the math to `app/engines/backtest/bs_pricing.py`
so the codebase has ONE source of truth for Black-Scholes — adding a second
implementation here would just guarantee they drift apart.

`bsm_greeks` is preserved as a 3-Greek (delta/vega/theta) back-compat
wrapper that returns the same PositionGreeks shape callers built against.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.engines.backtest.bs_pricing import (
    bs_delta, bs_gamma, bs_vega, bs_theta, bs_rho,
)


@dataclass
class GreeksBudget:
    """Portfolio Greek caps as fractions of NAV.
      • max_net_delta — |Σ delta·notional / NAV| cap
      • max_net_gamma — |Σ gamma·notional / NAV| cap (added Phase 0; the
        selector targets ATM gamma for scalping and gamma exposure
        snowballs near expiry, so it needs its own budget)
      • max_net_vega — |Σ vega·notional / NAV| cap
      • max_net_theta — lower bound; if Σ theta·notional / NAV < this,
        the portfolio is bleeding too fast on the long-vol side
    """
    max_net_delta: float = 0.30
    max_net_gamma: float = 0.05
    max_net_vega:  float = 0.15
    max_net_theta: float = -0.02


@dataclass
class PositionGreeks:
    """5-Greek position record. `gamma`/`rho` default to 0 so legacy callers
    that only populate delta/vega/theta keep type-checking. Use
    `bsm_greeks_full` to populate the full vector."""
    delta: float
    vega:  float
    theta: float
    gamma: float = 0.0
    rho:   float = 0.0


def bsm_greeks_full(
    S: float, K: float, T: float, r: float, sigma: float, is_call: bool
) -> PositionGreeks:
    """Full 5-Greek Black-Scholes evaluation.

    Args use the same shape as the legacy `bsm_greeks`:
      S, K   — spot, strike
      T      — time to expiry in YEARS
      r      — risk-free rate (decimal)
      sigma  — IV (decimal, e.g. 0.80 for 80% IV)
      is_call — True for call, False for put

    Returns PositionGreeks with delta/gamma/vega/theta/rho all populated.
    Delegates to bs_pricing so the BSM formulas live in exactly one place.
    Returns zeros when inputs are degenerate (T≤0 / sigma≤0 / S≤0 / K≤0).
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return PositionGreeks(0.0, 0.0, 0.0, 0.0, 0.0)
    dte_days = T * 365.0
    opt_type = "call" if is_call else "put"
    return PositionGreeks(
        delta=bs_delta(S, K, dte_days, sigma, opt_type),
        gamma=bs_gamma(S, K, dte_days, sigma),
        vega=bs_vega(S, K, dte_days, sigma),
        theta=bs_theta(S, K, dte_days, sigma, opt_type, r),
        rho=bs_rho(S, K, dte_days, sigma, opt_type, r),
    )


def bsm_greeks(
    S: float, K: float, T: float, r: float, sigma: float, is_call: bool
) -> PositionGreeks:
    """Back-compat 3-Greek wrapper around `bsm_greeks_full`.

    Existing callers only consume .delta/.vega/.theta — the extra
    gamma/rho fields on the returned PositionGreeks are harmless. New
    callers that need the full vector should call `bsm_greeks_full`
    directly for the intent to be explicit at the callsite.
    """
    return bsm_greeks_full(S, K, T, r, sigma, is_call)


class GreeksBudgetChecker:
    """Hard-gate any new option position against the portfolio Greek budget.

    Caller is responsible for refreshing the Greeks of each open position
    (re-running BSM at current spot/IV/T) BEFORE invoking `check` — the
    `getattr(p, 'greeks', None)` read is point-in-time and Greeks drift
    with the market. See `portfolio_greeks_aggregator.py` for the refresh
    helper used by the OrderRouter Phase-0 hard gate.
    """

    def __init__(self, budget: GreeksBudget, portfolio_value: float):
        self.budget = budget
        self.pv = portfolio_value

    def check(
        self,
        open_positions: list,
        new_position_greeks: PositionGreeks,
        new_position_notional: float,
    ) -> tuple[bool, str]:
        """Returns (allowed: bool, reason: str). reason is "ok" on pass,
        else "<greek>_breach:<actual_pct>><cap_pct>" — machine-readable so
        OrderRouter can echo it back as `code=greeks_budget_breach` with
        the breach detail."""
        net_delta = 0.0
        net_gamma = 0.0
        net_vega  = 0.0
        net_theta = 0.0
        for p in open_positions:
            g = getattr(p, 'greeks', None)
            n = getattr(p, 'notional', 0.0) or 0.0
            if g:
                net_delta += g.delta * n
                # Legacy PositionGreeks records (pre-Phase-0) lack gamma/rho;
                # default to 0 so old persisted positions don't blow up the gate.
                net_gamma += getattr(g, 'gamma', 0.0) * n
                net_vega  += g.vega  * n
                net_theta += g.theta * n

        net_delta += new_position_greeks.delta * new_position_notional
        net_gamma += new_position_greeks.gamma * new_position_notional
        net_vega  += new_position_greeks.vega  * new_position_notional
        net_theta += new_position_greeks.theta * new_position_notional

        if self.pv <= 0:
            return True, "ok"

        if abs(net_delta / self.pv) > self.budget.max_net_delta:
            return False, f"delta_breach:{net_delta/self.pv:.2%}>{self.budget.max_net_delta:.0%}"
        if abs(net_gamma / self.pv) > self.budget.max_net_gamma:
            return False, f"gamma_breach:{net_gamma/self.pv:.2%}>{self.budget.max_net_gamma:.0%}"
        if abs(net_vega / self.pv) > self.budget.max_net_vega:
            return False, f"vega_breach:{net_vega/self.pv:.2%}>{self.budget.max_net_vega:.0%}"
        if net_theta / self.pv < self.budget.max_net_theta:
            return False, f"theta_breach:{net_theta/self.pv:.2%}<{self.budget.max_net_theta:.0%}"

        return True, "ok"
