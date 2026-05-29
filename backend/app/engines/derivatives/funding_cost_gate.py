"""Funding-cost gate — hard cap on `funding_cost / expected_R`.

Plan-agent's correction: a softening factor on leverage produces values
that look reasonable but still bleed unprofitably. The correct rule is

  funding_cost_pct < profile.funding_cost_max_pct_of_R × expected_R_pct

where

  funding_cost_pct = funding_8h_pct × 3 × hold_days × leverage    (perps)
                   = 0                                            (options)
  expected_R_pct   = |stop_dist| / entry × rr

Returns (allowed, suggested_max_leverage, reason). When the requested
leverage breaches, we compute the largest leverage that satisfies the
ratio and downsize instead of rejecting outright — the chooser then
decides whether the downsized futures still beats the options
alternative.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FundingGateResult:
    allowed: bool
    max_leverage_for_budget: float
    projected_cost_usd: float
    projected_cost_pct_of_r: float
    reason: str = ""


def check(
    *,
    instrument_type: str,
    leverage: float,
    funding_8h_pct: float,
    hold_days: float,
    entry: float,
    stop_dist: float,
    rr: float,
    contracts: float,
    funding_cost_max_pct_of_R: float,
) -> FundingGateResult:
    """Returns a FundingGateResult. For options, always allowed and
    max_leverage_for_budget=1 (options have no funding charge in DEI's
    model — Plan agent confirmed)."""
    if instrument_type == "options":
        return FundingGateResult(
            allowed=True, max_leverage_for_budget=1.0,
            projected_cost_usd=0.0, projected_cost_pct_of_r=0.0,
        )
    if leverage <= 0 or entry <= 0 or stop_dist <= 0 or rr <= 0:
        return FundingGateResult(
            allowed=True, max_leverage_for_budget=max(1.0, leverage),
            projected_cost_usd=0.0, projected_cost_pct_of_r=0.0,
        )

    # 3 × hold_days because Delta India perps charge funding every 8h.
    notional = entry * contracts
    funding_cost_usd = funding_8h_pct * 3.0 * hold_days * leverage * notional
    expected_r_usd = (stop_dist / entry) * rr * notional
    if expected_r_usd <= 0:
        return FundingGateResult(
            allowed=True, max_leverage_for_budget=leverage,
            projected_cost_usd=funding_cost_usd,
            projected_cost_pct_of_r=0.0,
        )

    cost_pct_of_r = funding_cost_usd / expected_r_usd

    if cost_pct_of_r <= funding_cost_max_pct_of_R:
        return FundingGateResult(
            allowed=True, max_leverage_for_budget=leverage,
            projected_cost_usd=funding_cost_usd,
            projected_cost_pct_of_r=cost_pct_of_r,
        )

    # Solve for the leverage where cost_pct_of_r == cap:
    #   funding_8h × 3 × hold_days × lev / (stop_dist/entry × rr) == cap
    #   lev = cap × stop_dist/entry × rr / (funding_8h × 3 × hold_days)
    denom = funding_8h_pct * 3.0 * hold_days
    if denom <= 0:
        return FundingGateResult(
            allowed=True, max_leverage_for_budget=leverage,
            projected_cost_usd=funding_cost_usd,
            projected_cost_pct_of_r=cost_pct_of_r,
        )
    max_lev = funding_cost_max_pct_of_R * (stop_dist / entry) * rr / denom
    max_lev = max(1.0, max_lev)
    return FundingGateResult(
        allowed=False,
        max_leverage_for_budget=round(max_lev, 2),
        projected_cost_usd=funding_cost_usd,
        projected_cost_pct_of_r=cost_pct_of_r,
        reason=f"funding_breach:{cost_pct_of_r:.2%}>{funding_cost_max_pct_of_R:.0%}",
    )
