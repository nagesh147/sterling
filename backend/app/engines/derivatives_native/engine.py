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
    DecisionStatus, DerivativesDecision, DualDerivativesDecision,
    InstrumentBias, MarketContext, SignalContext, StrategyDerivativesProfile,
)
from app.engines.derivatives_native.config import DerivativesEngineConfig, RiskPosture
from app.schemas.market import OptionSummary


def _frozen_ok(candidate, *, reason: str, now_ms: int) -> DerivativesDecision:
    dec = DerivativesDecision(
        status=DecisionStatus.OK, chosen=candidate, alternatives=[],
        reason=reason, timestamp_ms=now_ms, warnings=list(candidate.warnings),
    )
    token, ttl = _get_freeze_store().freeze(dec)
    dec.freeze_token = token
    dec.freeze_token_ttl_ms = ttl
    return dec


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
    if (sources & {"vrp_voltiming", "skew_put"}) and chain:
        if cfg.risk_posture != RiskPosture.LONG_ONLY:
            warnings.append(
                f"risk_posture={cfg.risk_posture.value} not implemented in 2a; using long_only")
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
                code="no_options_candidate", timestamp_ms=now_ms,
            )

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
