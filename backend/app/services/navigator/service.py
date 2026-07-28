"""Navigator runtime service: per-user decision cache, the one safe
join point the scanner calls, the central-gate eligibility recheck, and
the price-feature-only evaluation pipeline (spec §16, §18).

This module owns ALL Navigator in-process mutable runtime state — nothing
else keeps its own copy. All state here is a CACHE: it is always safe to
drop and rebuild (e.g. on process restart), and restart never marks old
evidence as current (spec §18.3).

**Price-only mode.** Building live option-chain capture against a real
Kite account is the next integration step outside this session (it needs
a funded/authenticated account to exercise end-to-end). Per the spec's own
validation sequence (§19.3, step 1: "Run price-only walk-forward tests...
before enabling raw chain capture"), `evaluate_signal` runs correctly today
with `chain_history=None` / `gamma_context=None` — flow and gamma simply
report `quality="unavailable"` with `CHAIN_UNAVAILABLE`, exactly the state
the spec expects before chain capture is turned on.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from app.core.logging import get_logger
from app.engines.navigator import avwap, projected_ranges, volatility
from app.engines.navigator.fusion import FusionInputs, fuse
from app.engines.navigator.gamma_activity import GammaContractInput, evaluate_gamma_activity
from app.engines.navigator.option_flow import ChainFlowSample, evaluate_option_flow
from app.engines.navigator.quality import ValidatedCandles
from app.engines.navigator.schemas import (
    BaseSignalEvidence,
    DirectionalEvidence,
    NavigatorConfigModel,
    NavigatorDecision,
)
from app.engines.sterling_kite_engine.schemas import EngineSignalRow
from app.services import db
from app.services.navigator import config_store, repository
from app.services.navigator.status import ComponentStatus, NavigatorStatusSnapshot, build_status_snapshot

log = get_logger(__name__)

MODEL_VERSIONS = {
    "avwap": avwap.MODEL_VERSION,
    "ranges": projected_ranges.MODEL_VERSION,
    "volatility": volatility.MODEL_VERSION,
}

# uid -> {(underlying, token, direction): NavigatorDecision}
_decision_cache: dict[str, dict[tuple, NavigatorDecision]] = {}
# uid -> {component: ComponentStatus}
_component_status: dict[str, dict[str, ComponentStatus]] = {}
# uid -> bool — set True once a sampler/evaluation pass has actually run for this user
_sampler_running: dict[str, bool] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


# ─────────────────────────────────────────────────────────────────────────
# Decision cache + the scanner join point
# ─────────────────────────────────────────────────────────────────────────

def cache_decision(uid: str, *, underlying: str, token: int, direction: str, decision: NavigatorDecision) -> None:
    _decision_cache.setdefault(uid, {})[(underlying, token, direction)] = decision
    _sampler_running[uid] = True


def get_cached_decision(uid: str, *, underlying: str, token: int, direction: str) -> Optional[NavigatorDecision]:
    return _decision_cache.get(uid, {}).get((underlying, token, direction))


def get_cached_decisions_for_underlying(uid: str, underlying: str) -> list[NavigatorDecision]:
    return [d for (u, _tok, _dir), d in _decision_cache.get(uid, {}).items() if u == underlying]


def clear_cache(uid: str) -> None:
    """Test/reset hook — never called from production request paths."""
    _decision_cache.pop(uid, None)
    _component_status.pop(uid, None)
    _sampler_running.pop(uid, None)


def attach_to_rows(uid: str, rows: list[EngineSignalRow], *, default_underlyings: list[str]) -> list[EngineSignalRow]:
    """Synchronous, cache-only join — NEVER fetches live data or makes a
    broker call. Safe to call from the scanner's hot path once per scan.
    A disabled config makes this an exact no-op (`row.navigator` stays
    `None`, matching the field's default for every existing cached row)."""
    record = config_store.get(uid, default_underlyings=default_underlyings)
    if not record.config.enabled:
        return rows
    for row in rows:
        if not (row.is_fresh or row.is_active):
            continue
        decision = get_cached_decision(uid, underlying=row.underlying, token=row.token, direction=row.direction)
        if decision is not None and decision.config_revision == record.revision:
            row.navigator = decision
    return rows


def _check_execution_eligible_inner(uid: str, row: EngineSignalRow, *, default_underlyings: list[str]) -> tuple[bool, str]:
    record = config_store.get(uid, default_underlyings=default_underlyings)
    if not record.config.enabled or record.config.operating_mode != "gate":
        return True, "navigator_not_gating"
    if record.calibration_readiness != "ready":
        return False, "GATE_NOT_CALIBRATED"
    decision = get_cached_decision(uid, underlying=row.underlying, token=row.token, direction=row.direction)
    if decision is None:
        return False, "NO_DATA"
    if decision.config_revision != record.revision:
        return False, "CONFIG_REVISION_STALE"
    if decision.bar_close_ms < record.activation_watermark_ms:
        return False, "ACTIVATION_WATERMARK"
    if not decision.execution_eligible:
        return False, "NOT_ELIGIBLE"
    if not (row.is_fresh or row.is_active):
        return False, "BASE_SIGNAL_STALE"
    return True, "OK"


def check_execution_eligible(uid: str, row: EngineSignalRow, *, default_underlyings: list[str]) -> tuple[bool, str]:
    """Re-derives eligibility FRESH against CURRENT config — never trusts a
    cached decision's own `execution_eligible` flag for order submission.
    Returns `(True, "navigator_not_gating")` whenever Navigator isn't
    enabled in `gate` mode, which is a complete pass-through for every
    existing user (spec §16.3: the config revision must be re-read
    immediately before order submission; a disable/config change between
    scan and order blocks the order)."""
    eligible, reason = _check_execution_eligible_inner(uid, row, default_underlyings=default_underlyings)
    if not eligible:
        log.info("navigator.decision.blocked user=%s underlying=%s reason=%s", uid, row.underlying, reason)
    return eligible, reason


# ─────────────────────────────────────────────────────────────────────────
# Price-feature-only evaluation pipeline
# ─────────────────────────────────────────────────────────────────────────

def _placeholder_evidence(component: str, as_of_bar_close_ms: int, observed_at_ms: int) -> DirectionalEvidence:
    return DirectionalEvidence(
        component=component, as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
        direction=0, confidence_100=0.0, quality="unavailable", reason_codes=["CHAIN_UNAVAILABLE"], diagnostics={},
    )


def evaluate_signal(
    *,
    base: BaseSignalEvidence,
    candles: ValidatedCandles,
    config: NavigatorConfigModel,
    activation_watermark_ms: int,
    config_revision: int,
    generated_at_ms: Optional[int] = None,
    tick_size: float = 0.05,
    flow_sample: Optional[ChainFlowSample] = None,
    flow_history: Optional[list[ChainFlowSample]] = None,
    gamma_contracts: Optional[list[GammaContractInput]] = None,
    gamma_context: Optional[dict] = None,
    flow_required: bool = False,
    flow_not_applicable: bool = True,
    gamma_required: bool = False,
) -> NavigatorDecision:
    """Pure orchestration: base + candles (+ optional chain evidence) ->
    one immutable `NavigatorDecision`. No I/O — callers gather candles/chain
    data and pass them in, keeping this fully deterministic and testable."""
    generated_at_ms = generated_at_ms if generated_at_ms is not None else base.observed_at_ms
    bar_close_ms = int(candles.timestamp_ms[-1])

    range_eval = projected_ranges.evaluate_ranges(candles, config.ranges)
    atr_for_context = None  # avwap's own ATR isn't known yet at this point; range context falls back to its band-relative proxy

    def _range_supports(direction: str) -> Optional[bool]:
        ctx = range_eval.daily_context
        if ctx == "UNAVAILABLE":
            return None
        favorable = {"long": ("NEAR_UPPER", "BREAK_ABOVE", "REENTERED_FROM_ABOVE"), "short": ("NEAR_LOWER", "BREAK_BELOW", "REENTERED_FROM_BELOW")}
        return ctx in favorable[direction]

    structure, avwap_eval = avwap.evaluate_avwap(candles, config.avwap, range_supports=_range_supports(base.direction), tick_size=tick_size)
    avwap_evidence = _wrap_avwap(avwap_eval, bar_close_ms, generated_at_ms)

    mid_avwap = None if structure.warming_up[-1] else float(structure.mid[-1])
    volatility_eval = volatility.evaluate_volatility(candles, config.volatility, mid_avwap=mid_avwap, base_direction=base.direction)
    volatility_evidence = _wrap_volatility(volatility_eval, bar_close_ms, generated_at_ms)

    if flow_history:
        flow_eval = evaluate_option_flow(flow_history, config.flow)
        flow_evidence = _wrap_flow(flow_eval, bar_close_ms, generated_at_ms)
    else:
        flow_evidence = _placeholder_evidence("option_flow", bar_close_ms, generated_at_ms)

    if gamma_contracts is not None and gamma_context is not None:
        gamma_eval = evaluate_gamma_activity(
            contracts=gamma_contracts,
            flow_direction=flow_evidence.direction, flow_quality=flow_evidence.quality,
            config=config.gamma, **gamma_context,
        )
        gamma_evidence = _wrap_gamma(gamma_eval, bar_close_ms, generated_at_ms)
    else:
        gamma_evidence = _placeholder_evidence("gamma", bar_close_ms, generated_at_ms)

    range_impulse_supported = range_eval.daily_context in ("BREAK_ABOVE", "BREAK_BELOW") or range_eval.weekly_context in ("BREAK_ABOVE", "BREAK_BELOW")

    inputs = FusionInputs(
        base=base, avwap=avwap_evidence, avwap_grade=avwap_eval.grade.grade, avwap_is_fresh_signal=avwap_eval.family is not None,
        volatility=volatility_evidence, volatility_regime=volatility_eval.regime,
        flow=flow_evidence, flow_required=flow_required, flow_not_applicable=flow_not_applicable,
        gamma=gamma_evidence, gamma_required=gamma_required,
        range_impulse_supported=range_impulse_supported,
    )
    return fuse(
        inputs, config=config, activation_watermark_ms=activation_watermark_ms,
        generated_at_ms=generated_at_ms, config_revision=config_revision, model_versions=MODEL_VERSIONS,
    )


def _wrap_avwap(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import avwap_to_evidence
    return avwap_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def _wrap_volatility(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import volatility_to_evidence
    return volatility_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def _wrap_flow(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import option_flow_to_evidence
    return option_flow_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def _wrap_gamma(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import gamma_to_evidence
    return gamma_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def evaluate_and_cache(
    uid: str, row: EngineSignalRow, *, base: BaseSignalEvidence, candles: ValidatedCandles,
    config, activation_watermark_ms: int, config_revision: int, **kwargs,
) -> NavigatorDecision:
    """Evaluate one row and persist the resulting decision + feature
    snapshot, then cache it for `attach_to_rows`/`check_execution_eligible`
    — the one place a fresh decision enters the runtime."""
    decision = evaluate_signal(
        base=base, candles=candles, config=config, activation_watermark_ms=activation_watermark_ms,
        config_revision=config_revision, **kwargs,
    )
    cache_decision(uid, underlying=row.underlying, token=row.token, direction=row.direction, decision=decision)

    worst_quality = "ok"
    for evidence in (decision.avwap, decision.volatility, decision.option_flow, decision.gamma):
        if evidence is not None and evidence.quality == "unavailable":
            worst_quality = "degraded" if worst_quality == "ok" else worst_quality

    try:
        repository.insert_feature_snapshot({
            "user_id": uid, "underlying": row.underlying, "timeframe": base.timeframe,
            "bar_close_ms": decision.bar_close_ms, "observed_at_ms": decision.generated_at_ms,
            "config_revision": decision.config_revision, "model_versions_json": json.dumps(decision.model_versions),
            "quality": worst_quality,
            "avwap_json": decision.avwap.model_dump_json() if decision.avwap else None,
            "range_json": None,
            "volatility_json": decision.volatility.model_dump_json() if decision.volatility else None,
            "flow_json": decision.option_flow.model_dump_json() if decision.option_flow else None,
            "gamma_json": decision.gamma.model_dump_json() if decision.gamma else None,
            "input_hash": base.raw_payload_hash,
        })
        log.info(
            "navigator.feature.computed user=%s underlying=%s bar_close_ms=%s quality=%s",
            uid, row.underlying, decision.bar_close_ms, worst_quality,
        )
    except repository.NavigatorStorageError as exc:
        log.warning("Navigator feature snapshot persist failed for %s/%s: %s", uid, row.underlying, exc)

    try:
        repository.insert_signal_event({
            "decision_id": decision.decision_id, "user_id": uid, "underlying": row.underlying,
            "bar_close_ms": decision.bar_close_ms, "generated_at_ms": decision.generated_at_ms,
            "direction": decision.direction, "status": decision.status,
            "effective_score": decision.effective_score, "execution_eligible": int(decision.execution_eligible),
            "config_revision": decision.config_revision, "payload_json": decision.model_dump_json(),
        })
        log.info(
            "navigator.decision.emitted user=%s underlying=%s decision_id=%s status=%s effective_score=%s",
            uid, row.underlying, decision.decision_id, decision.status, decision.effective_score,
        )
    except repository.NavigatorStorageError as exc:
        log.warning("Navigator decision persist failed for %s/%s: %s", uid, row.underlying, exc)
    return decision


def get_feature_series(uid: str, underlying: str, *, timeframe: str = "60minute", since_bar_close_ms: int = 0, limit: int = 500) -> list[dict]:
    if not db.is_available():
        return []
    try:
        with db.connection() as c:
            rows = c.execute(
                "SELECT * FROM navigator_feature_snapshots WHERE user_id=? AND underlying=? AND timeframe=? "
                "AND bar_close_ms>=? ORDER BY bar_close_ms ASC LIMIT ?",
                (uid, underlying, timeframe, since_bar_close_ms, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Navigator feature series read failed for %s/%s: %s", uid, underlying, exc)
        return []


# ─────────────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────────────

def get_status(uid: str, *, default_underlyings: list[str]) -> NavigatorStatusSnapshot:
    record = config_store.get(uid, default_underlyings=default_underlyings)
    components = list(_component_status.get(uid, {}).values())
    last_decisions = [d.generated_at_ms for d in _decision_cache.get(uid, {}).values()]
    return build_status_snapshot(
        enabled=record.config.enabled, operating_mode=record.config.operating_mode,
        calibration_readiness=record.calibration_readiness, config_revision=record.revision,
        activation_watermark_ms=record.activation_watermark_ms, components=components,
        last_decision_at_ms=max(last_decisions) if last_decisions else None,
        sampler_running=_sampler_running.get(uid, False),
        now_ms=_now_ms(), max_feature_age_seconds=record.config.max_feature_age_seconds,
    )
