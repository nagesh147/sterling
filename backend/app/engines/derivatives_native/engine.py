"""Native derivatives engine producer.

Emits a futures leg and/or long-premium option legs per the active alpha
sources in `DerivativesEngineConfig`, gated only by tradeability + risk
posture — NOT by `instrument_chooser` (the routing veto). Returns the
existing `DualDerivativesDecision` contract so downstream is unchanged.

Phase 2a: directional_futures + long_only options (long call/put). Spreads
(defined_risk) and short vol (naked) are Phase 2b/2d; selecting them here
falls back to long_only with a warning.
"""
from __future__ import annotations

import time
from typing import Optional

from app.engines.derivatives import selector as _sel
from app.engines.derivatives.freeze_token import get_store as _get_freeze_store
from app.engines.derivatives.profiles import get_profile
from app.engines.derivatives.schemas import (
    DecisionStatus, DerivativesCandidate, DerivativesDecision, DualDerivativesDecision,
    InstrumentBias, MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives_native import regime as _regime
from app.engines.derivatives_native import structures as _structures
from app.engines.derivatives_native.config import DerivativesEngineConfig, RiskPosture
from app.schemas.market import OptionSummary


def _select_posture(allowed: set[str], ivr: Optional[float]) -> RiskPosture:
    """Pick the effective posture for the current regime from the *allowed* set.

    Multi-select: the user may enable several postures at once. Naked is only
    chosen when the regime is rich (high IV-rank); otherwise we fall down the
    priority chain (naked → defined_risk → long_only) to the richest *allowed*
    structure. Each engine branch keeps its own internal fallbacks (e.g. the
    naked branch warns and builds a defined-risk structure if a strangle can't
    be priced)."""
    if "naked" in allowed and ivr is not None and ivr >= _regime.RICH_IVR:
        return RiskPosture.NAKED
    if "defined_risk" in allowed:
        return RiskPosture.DEFINED_RISK
    if "long_only" in allowed:
        return RiskPosture.LONG_ONLY
    # Only naked is enabled but the regime isn't rich: hand to the naked branch,
    # which warns and falls back to a defined-risk structure.
    return RiskPosture.NAKED


def _frozen_ok(candidate, *, reason: str, now_ms: int) -> DerivativesDecision:
    dec = DerivativesDecision(
        status=DecisionStatus.OK, chosen=candidate, alternatives=[],
        reason=reason, timestamp_ms=now_ms, warnings=list(candidate.warnings),
    )
    token, ttl = _get_freeze_store().freeze(dec)
    dec.freeze_token = token
    dec.freeze_token_ttl_ms = ttl
    return dec


def _defined_risk_candidate(
    *, signal: SignalContext, market: MarketContext,
    profile: StrategyDerivativesProfile, chain: list[OptionSummary], sources: set[str],
) -> Optional[DerivativesCandidate]:
    """Build a defined-risk structure candidate based on the active source.
    Provisional rule (until Phase 1 calibrates): vrp→iron condor (sell vol),
    skew→put credit vertical, else debit vertical matching direction."""
    nav = market.portfolio_value
    max_loss_pct = profile.max_premium_pct_of_account
    width = 0.04
    if "vrp_voltiming" in sources:
        s = _structures.build_iron_condor(
            chain=chain, spot=market.spot, width_pct=width,
            nav_usd=nav, max_loss_pct=max_loss_pct)
    elif "skew_put" in sources:
        s = _structures.build_credit_vertical(
            chain=chain, spot=market.spot, direction=signal.direction,
            width_pct=width, nav_usd=nav, max_loss_pct=max_loss_pct)
    else:
        s = _structures.build_debit_vertical(
            chain=chain, spot=market.spot, direction=signal.direction,
            width_pct=width, nav_usd=nav, max_loss_pct=max_loss_pct)
    if s is None:
        return None
    return DerivativesCandidate(
        rank=0, instrument_type="options", underlying=signal.underlying,
        entry_price=signal.entry, direction=signal.direction,
        contracts=s.contracts, leverage=1.0,
        notional_usd=round(s.contracts * signal.entry, 2),
        premium_usd=round(s.net_premium_usd, 2),
        expected_r=(round(s.max_profit_usd / s.max_loss_usd, 3) if s.max_loss_usd > 0 else 0.0),
        score=1.0, structure=s,
    )


def _naked_candidate(
    *, signal: SignalContext, market: MarketContext,
    profile: StrategyDerivativesProfile, chain: list[OptionSummary],
) -> Optional[DerivativesCandidate]:
    """NAKED short strangle — UNCAPPED tail. Opt-in + regime-gated by the caller;
    sized to a premium budget; never auto-executed (auto-exec flags stay OFF)."""
    s = _structures.build_short_strangle(
        chain=chain, spot=market.spot, width_pct=0.04,
        nav_usd=market.portfolio_value, premium_pct=profile.max_premium_pct_of_account)
    if s is None:
        return None
    return DerivativesCandidate(
        rank=0, instrument_type="options", underlying=signal.underlying,
        entry_price=signal.entry, direction="neutral",
        contracts=s.contracts, leverage=1.0,
        notional_usd=round(s.contracts * signal.entry, 2),
        premium_usd=round(s.net_premium_usd, 2),
        expected_r=0.0, score=1.0, structure=s,
        warnings=["UNCAPPED TAIL RISK — naked short vol"],
    )


def _gex_iron_condor(
    *, chain: list[OptionSummary], signal: SignalContext,
    market: MarketContext, profile: StrategyDerivativesProfile,
    flip_level: float,
) -> Optional[DerivativesCandidate]:
    """GEX pinning trade: sell an iron condor centered on the zero-gamma-flip.

    Positive total GEX creates a dealer-gamma pinning effect — price tends to
    gravitate toward the flip level. Selling an iron condor around that level
    collects theta while the pin holds. Sized to the profile's max premium cap.
    """
    width = 0.03  # 3% wings for tight pinning
    s = _structures.build_iron_condor(
        chain=chain, spot=flip_level, width_pct=width,
        nav_usd=market.portfolio_value,
        max_loss_pct=profile.max_premium_pct_of_account,
    )
    if s is None:
        return None
    return DerivativesCandidate(
        rank=0, instrument_type="options", underlying=signal.underlying,
        entry_price=flip_level, direction="neutral",
        contracts=s.contracts, leverage=1.0,
        notional_usd=round(s.contracts * flip_level, 2),
        premium_usd=round(s.net_premium_usd, 2),
        expected_r=round(s.max_profit_usd / s.max_loss_usd, 3)
        if s.max_loss_usd > 0 else 0.0,
        score=1.0, structure=s,
        warnings=["GEX pinning trade — dealer gamma mean-reversion"],
    )


def _gex_directional(
    *, chain: list[OptionSummary], signal: SignalContext,
    market: MarketContext, profile: StrategyDerivativesProfile,
    gex_profile: dict, cfg_risk,
) -> Optional[DerivativesCandidate]:
    """GEX directional trade when total GEX is negative (trending regime).

    Negative GEX = dealers are short gamma → amplify moves. We trade
    directionally in the direction of the signal, using a debit vertical.
    """
    # Negative GEX acts as confirmation for the directional signal
    flip = gex_profile.get("zero_gamma_flip", market.spot)
    call_wall = gex_profile.get("call_wall", flip * 1.10)
    put_wall = gex_profile.get("put_wall", flip * 0.90)

    if signal.direction == "long":
        # Long above put wall — buying a debit call spread
        s = _structures.build_debit_vertical(
            chain=chain, spot=market.spot, direction="long",
            width_pct=0.04, nav_usd=market.portfolio_value,
            max_loss_pct=profile.max_premium_pct_of_account,
        )
    else:
        s = _structures.build_debit_vertical(
            chain=chain, spot=market.spot, direction="short",
            width_pct=0.04, nav_usd=market.portfolio_value,
            max_loss_pct=profile.max_premium_pct_of_account,
        )
    if s is None:
        return None
    return DerivativesCandidate(
        rank=0, instrument_type="options", underlying=signal.underlying,
        entry_price=signal.entry, direction=signal.direction,
        contracts=s.contracts, leverage=1.0,
        notional_usd=round(s.contracts * signal.entry, 2),
        premium_usd=round(s.net_premium_usd, 2),
        expected_r=round(s.max_profit_usd / s.max_loss_usd, 3)
        if s.max_loss_usd > 0 else 0.0,
        score=1.0, structure=s,
        warnings=[f"GEX directional: negative gamma ({gex_profile.get('total_gex',0):,.0f})"],
    )


def decide_both(
    *,
    signal: SignalContext,
    market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
    config: Optional[DerivativesEngineConfig] = None,
) -> DualDerivativesDecision:
    cfg = config or DerivativesEngineConfig()
    profile = get_profile(signal.strategy, profile_overrides)
    now_ms = int(time.time() * 1000)
    sources = set(cfg.active_alpha_sources)
    warnings: list[str] = []

    futures_leg: Optional[DerivativesDecision] = None
    options_leg: Optional[DerivativesDecision] = None

    # ── Futures leg (directional, default) — no routing veto ──────────────
    if "directional_futures" in sources:
        fut = _sel._futures_candidate(signal=signal, market=market, profile=profile)
        if fut is not None:
            futures_leg = _frozen_ok(fut, reason="native:directional_futures", now_ms=now_ms)
        else:
            futures_leg = DerivativesDecision(
                status=DecisionStatus.DEFER,
                reason=f"native futures sl_tp rejected for {signal.underlying}",
                code="sl_tp_reject", timestamp_ms=now_ms,
            )

    # ── Options leg (long premium only in 2a) ─────────────────────────────
    if (sources & {"vrp_voltiming", "skew_put", "directional_options", "gex_pinning"}) and chain:
        # GEX pinning: when active AND we have a GEX profile, build a
        # non-directional structure (iron condor) around the zero-gamma-flip
        # level. Falls through to other sources if GEX data isn't available.
        if "gex_pinning" in sources and market.gex_profile is not None:
            gex = market.gex_profile
            total_gex = gex.get("total_gex", 0.0)
            flip = gex.get("zero_gamma_flip", market.spot)
            # GEX pinning: sell vol around the flip level when GEX is
            # strongly positive (mean-reverting regime). Iron condor centered
            # on the flip level with wide wings.
            if abs(total_gex) > 50_000:
                if total_gex > 0:
                    # Positive GEX → mean-reverting → sell an iron condor
                    cand = _gex_iron_condor(
                        chain=chain, signal=signal, market=market,
                        profile=profile, flip_level=flip)
                    if cand is not None:
                        cand.warnings.append(
                            f"gex_pinning: total_gex={total_gex:,.0f} flip={flip:.0f}")
                        options_leg = _frozen_ok(
                            cand, reason="native:gex_pinning", now_ms=now_ms)
                else:
                    # Negative GEX → trending → directional options or futures
                    # Defer to directional_futures or directional_options if active;
                    # otherwise treat as a gamma-short directional signal.
                    if sources & {"directional_futures", "directional_options"}:
                        warnings.append(
                            f"gex_pinning: negative GEX ({total_gex:,.0f}) — "
                            f"deferring to directional sources")
                    else:
                        # No directional source active: use GEX signal as
                        # directional trigger (short at call wall, long at put wall)
                        cand = _gex_directional(
                            chain=chain, signal=signal, market=market,
                            profile=profile, gex_profile=gex, cfg_risk=cfg.risk_posture)
                        if cand is not None:
                            options_leg = _frozen_ok(
                                cand, reason="native:gex_pinning:directional", now_ms=now_ms)

        if options_leg is None and (sources & {"vrp_voltiming", "skew_put", "directional_options"}):
            pass  # Fall through to other option sources if GEX didn't generate a trade

        if options_leg is None:
            effective_posture = _select_posture(set(cfg.risk_postures), market.ivr_pct)
            if effective_posture == RiskPosture.NAKED:
                # Naked is gated on a RICH vol regime (high IV-rank). Otherwise we do
                # NOT sell cheap vol naked — fall back to defined-risk.
                ivr = market.ivr_pct
                if ivr is not None and ivr >= _regime.RICH_IVR:
                    cand = _naked_candidate(
                        signal=signal, market=market, profile=profile, chain=chain)
                    if cand is not None:
                        warnings.append(
                            "naked short vol — UNCAPPED TAIL RISK (opt-in; never auto-executed)")
                        options_leg = _frozen_ok(cand, reason="native:naked_short_vol", now_ms=now_ms)
                    else:
                        options_leg = DerivativesDecision(
                            status=DecisionStatus.DEFER,
                            reason="no naked structure buildable from chain",
                            code="no_structure", timestamp_ms=now_ms)
                else:
                    warnings.append(
                        f"naked requested but regime not rich (ivr={ivr}); using defined_risk")
                    cand = _defined_risk_candidate(
                        signal=signal, market=market, profile=profile, chain=chain, sources=sources)
                    options_leg = (
                        _frozen_ok(cand, reason="native:defined_risk", now_ms=now_ms)
                        if cand is not None else DerivativesDecision(
                            status=DecisionStatus.DEFER,
                            reason="no defined-risk structure buildable from chain",
                            code="no_structure", timestamp_ms=now_ms))
            elif effective_posture == RiskPosture.DEFINED_RISK:
                cand = _defined_risk_candidate(
                    signal=signal, market=market, profile=profile, chain=chain, sources=sources)
                if cand is not None:
                    options_leg = _frozen_ok(cand, reason="native:defined_risk", now_ms=now_ms)
                else:
                    options_leg = DerivativesDecision(
                        status=DecisionStatus.DEFER,
                        reason="no defined-risk structure buildable from chain",
                        code="no_structure", timestamp_ms=now_ms)
            else:
                # long_only: single long premium via the existing builder.
                # Native ignores per-strategy instrument_bias so options aren't suppressed.
                opt_profile = profile.model_copy(update={"instrument_bias": InstrumentBias.AUTO})
                opts = _sel._build_options_candidates(
                    signal=signal, market=market, profile=opt_profile, chain=chain)
                if opts:
                    options_leg = _frozen_ok(opts[0], reason="native:long_premium", now_ms=now_ms)
                    options_leg.alternatives = opts[1:4]
                else:
                    options_leg = DerivativesDecision(
                        status=DecisionStatus.DEFER,
                        reason="no long-premium strike survived tradeability gates",
                        code="no_options_candidate", timestamp_ms=now_ms)

    status = DecisionStatus.OK if (
        (futures_leg and futures_leg.status == DecisionStatus.OK)
        or (options_leg and options_leg.status == DecisionStatus.OK)
    ) else DecisionStatus.DEFER

    return DualDerivativesDecision(
        status=status, futures=futures_leg, options=options_leg,
        reason=f"native mode · sources={sorted(sources)}",
        timestamp_ms=now_ms, warnings=warnings,
    )


def decide(
    *,
    signal: SignalContext,
    market: MarketContext,
    chain: Optional[list[OptionSummary]] = None,
    profile_overrides: Optional[dict[str, StrategyDerivativesProfile]] = None,
    config: Optional[DerivativesEngineConfig] = None,
) -> DerivativesDecision:
    """Single-decision shape for /preview parity: prefer options leg if OK,
    else futures leg, else a DEFER."""
    dual = decide_both(signal=signal, market=market, chain=chain,
                       profile_overrides=profile_overrides, config=config)
    if dual.options and dual.options.status == DecisionStatus.OK:
        return dual.options
    if dual.futures and dual.futures.status == DecisionStatus.OK:
        return dual.futures
    return DerivativesDecision(
        status=DecisionStatus.DEFER, reason=dual.reason,
        code="native_no_candidate", timestamp_ms=dual.timestamp_ms)
