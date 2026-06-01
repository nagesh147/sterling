"""DerivativesSelector — top-level orchestrator.

Pipeline (matches the diagram in nifty-honking-pudding.md):
  1. profile.enabled gate (returns PROFILE_OFF when False)
  2. instrument_chooser runs in two passes — first WITHOUT options data
     to decide whether to even look at the chain, then re-runs after
     scoring options to confirm the choice
  3. if options: expiry_picker → strike_picker → time_shifted_revaluation
     (already inside picker) → pinning_gate → liquidity ranking
  4. if futures: sl_tp_solver_futures
  5. funding_cost_gate + leverage_engine (futures only)
  6. Greeks budget soft gate via portfolio_greeks_aggregator
  7. Build DerivativesDecision, freeze it, return

Caller (strategy /execute endpoint) builds a SignalContext + MarketContext
and gets a DerivativesDecision back. The decision either has a chosen
candidate + freeze_token (status=OK) or a reason for not picking
(status ∈ {DEFER, FAIL_OPEN, PROFILE_OFF}).
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from app.engines.derivatives import (
    funding_cost_gate, instrument_chooser, leverage_engine, pinning_gate,
    profiles as profiles_mod, sl_tp_solver, strike_picker, expiry_picker,
)
from app.engines.derivatives.freeze_token import get_store as get_freeze_store
from app.engines.derivatives.schemas import (
    DecisionStatus, DerivativesCandidate, DerivativesDecision,
    DualDerivativesDecision, InstrumentBias, LiquidityScore,
    MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives.strike_picker import ScoredStrike
from app.schemas.market import OptionSummary

log = logging.getLogger(__name__)


def _hold_days(profile: StrategyDerivativesProfile, override_minutes: Optional[int]) -> float:
    minutes = override_minutes if override_minutes is not None else profile.expected_hold_minutes
    return max(0.0, minutes / (24 * 60))


def _futures_candidate(
    *, signal: SignalContext, market: MarketContext,
    profile: StrategyDerivativesProfile,
) -> Optional[DerivativesCandidate]:
    """Build a futures candidate: solve SL/TP via the existing solver,
    run funding gate to size leverage, run leverage_engine for the final
    leverage."""
    sl_plan = sl_tp_solver.solve_futures(
        direction=signal.direction, entry=signal.entry,
        structure_stop=signal.stop_loss, atr_val=signal.atr,
        take_profit=signal.take_profit, rr=signal.rr_target,
        validated=signal.presized,
    )
    if not sl_plan.ok:
        log.info("futures sl_tp rejected for %s: %s", signal.underlying, sl_plan.reason)
        return None

    # Provisional leverage = profile cap; funding gate cuts it down
    provisional_lev = float(profile.leverage_cap)
    stop_dist = abs(signal.entry - sl_plan.stop_loss)
    funding_res = funding_cost_gate.check(
        instrument_type="futures",
        leverage=provisional_lev,
        funding_8h_pct=market.funding_8h_pct or 0.0,
        hold_days=_hold_days(profile, signal.expected_hold_minutes),
        entry=signal.entry, stop_dist=stop_dist, rr=signal.rr_target,
        contracts=1.0, funding_cost_max_pct_of_R=profile.funding_cost_max_pct_of_R,
    )
    lev = leverage_engine.decide(
        instrument_type="futures", underlying=signal.underlying,
        profile=profile, market=market, funding_result=funding_res,
        requested_leverage=provisional_lev,
    )

    # Risk-based sizing: contracts so that max_risk_usd = risk_pct × NAV
    risk_per_R_usd = market.portfolio_value * 0.02      # 2% per R baseline
    contracts = max(0.01, round(risk_per_R_usd / max(1e-9, stop_dist), 4))
    notional = contracts * signal.entry

    return DerivativesCandidate(
        rank=0,
        instrument_type="futures",
        underlying=signal.underlying,
        entry_price=signal.entry,
        direction=signal.direction,
        contracts=contracts,
        leverage=lev.leverage,
        notional_usd=round(notional, 2),
        stop_loss=sl_plan.stop_loss,
        take_profit=sl_plan.take_profit,
        expected_r=sl_plan.rr,
        projected_funding_cost_usd=round(funding_res.projected_cost_usd, 2),
        score=1.0,
        score_breakdown=lev.components,
        warnings=lev.warnings,
    )


def _options_candidate_from_strike(
    *, strike: ScoredStrike, signal: SignalContext,
    market: MarketContext, profile: StrategyDerivativesProfile, rank: int,
) -> Optional[DerivativesCandidate]:
    o = strike.option
    if strike.premium_at_tp <= 0 or strike.premium_at_sl < 0:
        return None

    entry_premium = o.mark_price if o.mark_price > 0 else o.mid_price
    expected_hold_days = getattr(profile, "expected_hold_minutes", 60) / 1440.0
    current_iv = o.mark_iv / 100.0 if o.mark_iv > 5.0 else o.mark_iv
    sl_plan = sl_tp_solver.solve_options(
        direction=signal.direction, entry_spot=signal.entry,
        stop_spot=signal.stop_loss, target_spot=signal.take_profit or signal.entry,
        premium_now=entry_premium,
        premium_at_tp=strike.premium_at_tp,
        premium_at_sl=strike.premium_at_sl,
        expected_hold_days=expected_hold_days,
        current_iv=current_iv,
        entry_iv=current_iv,
    )

    # Premium-budget cap: notional = contracts × premium ≤ profile.max_premium_pct × NAV
    nav_cap_usd = market.portfolio_value * profile.max_premium_pct_of_account
    entry_premium = o.mark_price if o.mark_price > 0 else o.mid_price
    if entry_premium <= 0:
        return None
    contracts = max(0.01, round(nav_cap_usd / entry_premium, 4))
    notional = contracts * signal.entry        # spot notional for Greeks budget denomination
    premium_usd = contracts * entry_premium

    # Theta burn projected $ — premium × theta_burn_pct × contracts
    projected_theta_burn = round(entry_premium * strike.theta_burn_pct * contracts, 2)

    return DerivativesCandidate(
        rank=rank,
        instrument_type="options",
        underlying=signal.underlying,
        option_symbol=o.instrument_name,
        option_type=o.option_type,
        strike=o.strike,
        expiry=o.expiry_date,
        dte=o.dte,
        entry_price=signal.entry,
        direction=signal.direction,
        contracts=contracts,
        leverage=1.0,
        notional_usd=round(notional, 2),
        premium_usd=round(premium_usd, 2),
        stop_loss=sl_plan.stop_loss,
        take_profit=sl_plan.take_profit,
        sl_premium=sl_plan.sl_premium,
        tp_premium=sl_plan.tp_premium,
        expected_r=round(strike.expected_r, 3),
        projected_theta_burn_usd=projected_theta_burn,
        delta=o.delta, gamma=o.gamma, vega=o.vega, theta=o.theta, rho=o.rho,
        liquidity=strike.liquidity,
        spread_pct=o.spread_pct,
        open_interest=o.open_interest,
        mark_iv=o.mark_iv,
        score=round(strike.composite, 4),
        score_breakdown=strike.breakdown,
    )


def _build_options_candidates(
    *, signal: SignalContext, market: MarketContext,
    profile: StrategyDerivativesProfile,
    chain: Optional[list[OptionSummary]],
) -> list[DerivativesCandidate]:
    """Reusable: run expiry → strike → pinning gates and return top-N
    options candidates. Tries alternative expiries if the preferred
    one gets completely vetoed (e.g., by pinning risk).
    Empty list when chain is missing, profile bias is FUTURES, or
    no strike survives the gates."""
    if profile.instrument_bias == InstrumentBias.FUTURES or not chain:
        return []
        
    grouped = expiry_picker.candidate_expiries(chain, profile, signal.expected_hold_minutes)
    if not grouped:
        return []

    wanted_type = "call" if signal.direction == "long" else "put"
    hold_days = _hold_days(profile, signal.expected_hold_minutes)
    spot_tp = signal.take_profit or signal.entry
    spot_sl = signal.stop_loss

    for (dte, expiry), expiry_candidates in grouped.items():
        expiry_filtered = [o for o in expiry_candidates if o.option_type == wanted_type]
        if not expiry_filtered:
            continue
            
        ranked = strike_picker.pick(
            candidates=expiry_filtered, profile=profile, spot=market.spot,
            spot_tp=spot_tp, spot_sl=spot_sl,
            expected_hold_days=hold_days,
            prefer_gamma=profile.expected_hold_minutes < 60 * 6,
            full_chain=chain,
        )
        
        kept = [s for s in ranked if not s.drop_reason]
        if not kept:
            continue
            
        kept_post_pin: list[ScoredStrike] = []
        for s in kept:
            pr = pinning_gate.check_pinning(s.option, market.spot, chain)
            if pr.veto:
                s.drop_reason = pr.reason
            else:
                kept_post_pin.append(s)
                
        if kept_post_pin:
            out: list[DerivativesCandidate] = []
            for idx, s in enumerate(kept_post_pin[:4]):
                cand = _options_candidate_from_strike(
                    strike=s, signal=signal, market=market, profile=profile, rank=idx,
                )
                if cand:
                    out.append(cand)
            if out:
                return out

    return []


def decide(
    *,
    signal: SignalContext,
    market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
) -> DerivativesDecision:
    """Top-level entry: pick the best instrument+strike+leverage for `signal`.

    `chain` is the option chain for `signal.underlying`. Passed in by the
    caller (api endpoint) which is responsible for batching one fetch per
    underlying per request. None → futures-only.
    """
    now_ms = int(time.time() * 1000)
    profile = profiles_mod.get_profile(signal.strategy, profile_overrides)

    # 1. Profile gate
    if not profile.enabled:
        return DerivativesDecision(
            status=DecisionStatus.PROFILE_OFF,
            reason=f"profile {signal.strategy} is disabled — strategy uses legacy futures path",
            code="profile_off",
            timestamp_ms=now_ms,
        )

    # 2. Build best options candidate (if profile allows and chain present)
    options_candidates: list[DerivativesCandidate] = _build_options_candidates(
        signal=signal, market=market, profile=profile, chain=chain,
    )

    best_option_r = options_candidates[0].expected_r if options_candidates else None
    best_option_spread = options_candidates[0].spread_pct if options_candidates else None
    best_option_gamma = options_candidates[0].gamma if options_candidates else None
    
    # GEX Calculation
    gex_influence = 50.0
    if chain:
        from app.engines.derivatives.gex_engine import calculate_gex_profile, get_gex_routing_influence
        gex_prof = calculate_gex_profile(chain, market.spot)
        gex_influence = get_gex_routing_influence(gex_prof, market.spot)

    chooser = instrument_chooser.choose(
        signal=signal, profile=profile, market=market,
        best_option_expected_r=best_option_r,
        best_option_spread=best_option_spread,
        best_option_gamma=best_option_gamma,
        gex_influence_score=gex_influence,
    )

    if chooser.instrument_type == "options" and options_candidates:
        chosen = options_candidates[0]
        alternatives = options_candidates[1:4]
    else:
        # Futures path — build the futures candidate
        futures_cand = _futures_candidate(signal=signal, market=market, profile=profile)
        if futures_cand is None:
            return DerivativesDecision(
                status=DecisionStatus.DEFER,
                reason=f"futures sl_tp_solver rejected: {signal.underlying} setup not tradeable",
                code="sl_tp_reject",
                timestamp_ms=now_ms,
            )
        chosen = futures_cand
        # Show top option candidates as alternatives if any
        alternatives = options_candidates[:3] if options_candidates else []

    # 4. Freeze the decision so /execute can validate the token
    decision = DerivativesDecision(
        status=DecisionStatus.OK,
        chosen=chosen,
        alternatives=alternatives,
        reason=f"{chooser.instrument_type} via {chooser.reason}",
        timestamp_ms=now_ms,
        warnings=list(chosen.warnings),
    )
    token, ttl = get_freeze_store().freeze(decision)
    decision.freeze_token = token
    decision.freeze_token_ttl_ms = ttl
    return decision


def decide_both(
    *,
    signal: SignalContext,
    market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
) -> DualDerivativesDecision:
    """Co-emit best-futures + best-options candidates for ONE signal.

    Used by the FE which renders two parallel tables (one per instrument
    type) and by the background scanner which auto-executes based on
    `profile.auto_execute_futures` / `profile.auto_execute_options`
    independently.

    Each leg carries its own freeze_token; consuming one does not
    invalidate the other. A profile in FUTURES bias returns
    options=None; OPTIONS bias returns futures=None. AUTO bias returns
    both legs whenever both are feasible.
    """
    now_ms = int(time.time() * 1000)
    profile = profiles_mod.get_profile(signal.strategy, profile_overrides)

    if not profile.enabled:
        return DualDerivativesDecision(
            status=DecisionStatus.PROFILE_OFF,
            reason=f"profile {signal.strategy} is disabled",
            code="profile_off",
            timestamp_ms=now_ms,
        )

    futures_leg: Optional[DerivativesDecision] = None
    options_leg: Optional[DerivativesDecision] = None

    # ── Futures leg ────────────────────────────────────────────────────
    if profile.instrument_bias != InstrumentBias.OPTIONS:
        fut = _futures_candidate(signal=signal, market=market, profile=profile)
        if fut is not None:
            futures_decision = DerivativesDecision(
                status=DecisionStatus.OK,
                chosen=fut,
                alternatives=[],
                reason="futures via decide_both",
                timestamp_ms=now_ms,
                warnings=list(fut.warnings),
            )
            token, ttl = get_freeze_store().freeze(futures_decision)
            futures_decision.freeze_token = token
            futures_decision.freeze_token_ttl_ms = ttl
            futures_leg = futures_decision
        else:
            futures_leg = DerivativesDecision(
                status=DecisionStatus.DEFER,
                reason=f"futures sl_tp_solver rejected for {signal.underlying}",
                code="sl_tp_reject",
                timestamp_ms=now_ms,
            )

    # ── Options leg ────────────────────────────────────────────────────
    if profile.instrument_bias != InstrumentBias.FUTURES:
        opts = _build_options_candidates(
            signal=signal, market=market, profile=profile, chain=chain,
        )
        if opts:
            options_decision = DerivativesDecision(
                status=DecisionStatus.OK,
                chosen=opts[0],
                alternatives=opts[1:4],
                reason="options via decide_both",
                timestamp_ms=now_ms,
                warnings=list(opts[0].warnings),
            )
            token, ttl = get_freeze_store().freeze(options_decision)
            options_decision.freeze_token = token
            options_decision.freeze_token_ttl_ms = ttl
            options_leg = options_decision
        else:
            options_leg = DerivativesDecision(
                status=DecisionStatus.DEFER,
                reason=(
                    "no option chain" if not chain
                    else "no strike survived gates (liquidity / pinning / IVR)"
                ),
                code="no_options_candidate",
                timestamp_ms=now_ms,
            )

    # OK if at least one leg landed an OK candidate
    status = DecisionStatus.OK if (
        (futures_leg and futures_leg.status == DecisionStatus.OK)
        or (options_leg and options_leg.status == DecisionStatus.OK)
    ) else DecisionStatus.DEFER

    return DualDerivativesDecision(
        status=status,
        futures=futures_leg,
        options=options_leg,
        reason=f"bias={profile.instrument_bias.value}",
        timestamp_ms=now_ms,
    )
