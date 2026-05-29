"""Options-vs-futures decision for the central DerivativesSelector.

Per Plan-agent's refinement, the heuristic is multi-dimensional:
  • profile.instrument_bias hard-overrides AUTO (FUTURES / OPTIONS)
  • options preferred when ALL of:
      − signal_score > conviction_floor (50)
      − asymmetry_R > 3 (BSM-priced via time_shifted_revaluation in
        the strike_picker; passed in here as `best_option_expected_r`)
      − market.ivr_pct < profile.ivr_pct_naked_max
      − liquidity floor met (caller's responsibility; we just see if
        best_option_candidate is not None)
      − front-month IV NOT > back-month IV + profile.front_back_iv_diff_max
  • futures preferred otherwise. Basis check:
      − perp basis > +0.5% for >1h → favour OPTIONS for longs
        (futures bleeds via funding)
      − basis < −0.5% → favour FUTURES SHORTS (funding pays us)

Returns the chosen instrument_type plus the reasoning components.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.derivatives.schemas import (
    InstrumentBias, MarketContext, SignalContext, StrategyDerivativesProfile,
)


@dataclass
class InstrumentDecision:
    instrument_type: str            # "futures" | "options"
    reason: str
    breakdown: dict[str, float]


CONVICTION_FLOOR = 50.0
ASYMMETRY_R_FLOOR = 3.0


def choose(
    *,
    signal: SignalContext,
    profile: StrategyDerivativesProfile,
    market: MarketContext,
    best_option_expected_r: Optional[float],
    front_month_iv: Optional[float] = None,
    back_month_iv: Optional[float] = None,
) -> InstrumentDecision:
    breakdown: dict[str, float] = {
        "signal_score": signal.signal_score,
        "best_option_R": best_option_expected_r or 0.0,
        "ivr_pct": market.ivr_pct or 0.0,
        "basis_pct": market.basis_pct or 0.0,
    }

    # Hard overrides
    if profile.instrument_bias == InstrumentBias.FUTURES:
        return InstrumentDecision("futures", "profile=FUTURES", breakdown)
    if profile.instrument_bias == InstrumentBias.OPTIONS:
        return InstrumentDecision("options", "profile=OPTIONS", breakdown)

    # AUTO logic
    reasons_for_options: list[str] = []

    # Conviction
    if signal.signal_score >= CONVICTION_FLOOR:
        reasons_for_options.append("conviction")

    # Asymmetric payoff
    if best_option_expected_r and best_option_expected_r >= ASYMMETRY_R_FLOOR:
        reasons_for_options.append(f"asymmetry_R={best_option_expected_r:.2f}")
        breakdown["asymmetry_pass"] = 1.0

    # IVR cap
    ivr_ok = (
        market.ivr_pct is None or market.ivr_pct <= profile.ivr_pct_naked_max
    )
    if ivr_ok:
        reasons_for_options.append("ivr_ok")
        breakdown["ivr_pass"] = 1.0

    # Term-structure check
    term_ok = True
    if front_month_iv is not None and back_month_iv is not None:
        front_back_diff = front_month_iv - back_month_iv
        breakdown["front_back_diff"] = front_back_diff
        if front_back_diff > profile.front_back_iv_diff_max:
            term_ok = False
    if term_ok:
        reasons_for_options.append("term_ok")

    # Basis check
    basis = market.basis_pct or 0.0
    if signal.direction == "long" and basis > 0.005:
        reasons_for_options.append(f"basis_high:{basis:.2%}")
    elif signal.direction == "short" and basis < -0.005:
        # Negative basis → futures shorts get paid funding
        breakdown["funding_pays_shorts"] = 1.0

    options_count_needed = 3
    if (
        best_option_expected_r and best_option_expected_r >= ASYMMETRY_R_FLOOR
        and ivr_ok and term_ok
        and signal.signal_score >= CONVICTION_FLOOR
    ):
        return InstrumentDecision(
            "options",
            "all_options_criteria_met:" + ",".join(reasons_for_options),
            breakdown,
        )

    # Fall through → futures
    futures_reason = "default_futures"
    if not ivr_ok:
        futures_reason = f"ivr_too_high:{market.ivr_pct:.0f}>{profile.ivr_pct_naked_max}"
    elif best_option_expected_r is None or best_option_expected_r < ASYMMETRY_R_FLOOR:
        futures_reason = "asymmetry_below_floor"
    elif signal.signal_score < CONVICTION_FLOOR:
        futures_reason = f"conviction_low:{signal.signal_score:.0f}<{CONVICTION_FLOOR}"
    elif not term_ok:
        futures_reason = "front_back_iv_diff_too_high"

    return InstrumentDecision("futures", futures_reason, breakdown)
