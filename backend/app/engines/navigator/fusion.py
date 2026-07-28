"""Event-time join, hard-gate truth table, scoring, and immutable decision
generation (spec §13).

Fusion never places an order and never sets the FINAL execution-eligible
truth on its own — `NavigatorDecision.execution_eligible` here only mirrors
`status in (CONFIRMED, HIGH_CONVICTION)`, computed at scan time. The
central order gate (Phase 5, `service.py`) always re-derives real
eligibility fresh at submission time (current config revision, operating
mode, calibration readiness, watermark) — this field is one input to that
gate, never a substitute for it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from app.engines.navigator.avwap import AvwapEvaluation, AvwapGradeLabel
from app.engines.navigator.gamma_activity import GammaEvaluation
from app.engines.navigator.option_flow import OptionFlowEvaluation
from app.engines.navigator.schemas import (
    BaseSignalEvidence,
    DirectionalEvidence,
    NavigatorDecision,
    ReasonCode,
    canonical_json_hash,
)
from app.engines.navigator.volatility import VolatilityEvaluation

MODEL_VERSION = "fusion_v1"

_GRADE_RANK = {"A+": 3, "A": 2, "B": 1, "none": 0}


def _grade_meets_min(grade: AvwapGradeLabel, min_grade: str) -> bool:
    return _GRADE_RANK.get(grade, 0) >= _GRADE_RANK.get(min_grade, 0)


# ─────────────────────────────────────────────────────────────────────────
# Wrap each component's own evaluation dataclass into `DirectionalEvidence`
# ─────────────────────────────────────────────────────────────────────────

def avwap_to_evidence(evaluation: AvwapEvaluation, *, as_of_bar_close_ms: int, observed_at_ms: int) -> DirectionalEvidence:
    if evaluation.warming_up:
        return DirectionalEvidence(
            component="avwap", as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
            direction=0, confidence_100=0.0, quality="unavailable", reason_codes=["AVWAP_WARMING_UP"], diagnostics={},
        )
    if evaluation.family is None:
        return DirectionalEvidence(
            component="avwap", as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
            direction=0, confidence_100=0.0, quality="ok", reason_codes=["OK"],
            diagnostics={"grade": evaluation.grade.grade, "family": None},
        )
    return DirectionalEvidence(
        component="avwap", as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
        direction=evaluation.direction, confidence_100=evaluation.grade.score, quality="ok", reason_codes=["OK"],
        diagnostics={"grade": evaluation.grade.grade, "family": evaluation.family},
    )


def volatility_to_evidence(evaluation: VolatilityEvaluation, *, as_of_bar_close_ms: int, observed_at_ms: int) -> DirectionalEvidence:
    quality: Literal["ok", "degraded", "unavailable"] = "unavailable" if evaluation.regime is None else "ok"
    direction = {"LONG": 1, "SHORT": -1, "WAIT": 0}[evaluation.direction]
    valid_reasons = [r for r in evaluation.reason_codes if r in ReasonCode.__args__]
    return DirectionalEvidence(
        component="volatility", as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
        direction=direction, confidence_100=evaluation.confidence_100 if quality == "ok" else 0.0,
        quality=quality, reason_codes=valid_reasons or ["OK"],
        diagnostics={"regime": evaluation.regime, "flip_age_bars": evaluation.flip_age_bars, "late_flip": evaluation.late_flip},
    )


def option_flow_to_evidence(evaluation: OptionFlowEvaluation, *, as_of_bar_close_ms: int, observed_at_ms: int) -> DirectionalEvidence:
    valid_reasons = [r for r in evaluation.reason_codes if r in ReasonCode.__args__]
    return DirectionalEvidence(
        component="option_flow", as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
        direction=evaluation.direction, confidence_100=evaluation.confidence_100, quality=evaluation.quality,
        reason_codes=valid_reasons or ["OK"],
        diagnostics={"oscillator": evaluation.oscillator, "state": evaluation.state},
    )


def gamma_to_evidence(evaluation: GammaEvaluation, *, as_of_bar_close_ms: int, observed_at_ms: int) -> DirectionalEvidence:
    valid_reasons = [r for r in evaluation.reason_codes if r in ReasonCode.__args__]
    return DirectionalEvidence(
        component="gamma", as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
        direction=evaluation.direction, confidence_100=evaluation.confidence_100, quality=evaluation.quality,
        reason_codes=valid_reasons or ["OK"],
        diagnostics={"is_event": evaluation.is_event, "level_z": evaluation.level_z, "expiry_profile": evaluation.expiry_profile},
    )


# ─────────────────────────────────────────────────────────────────────────
# Trigger rule (spec §13.2)
# ─────────────────────────────────────────────────────────────────────────

def _bars_apart(a_ms: int, b_ms: int, timeframe_ms: int) -> int:
    return abs(a_ms - b_ms) // max(timeframe_ms, 1)


def determine_trigger(
    base: BaseSignalEvidence, avwap_evidence: DirectionalEvidence, avwap_is_fresh_signal: bool,
    event_alignment_bars: int, timeframe_ms: int,
) -> Optional[Literal["base_fresh", "avwap_fresh"]]:
    avwap_initialized = avwap_evidence.quality != "unavailable"
    if base.state == "fresh" and avwap_initialized:
        return "base_fresh"
    if avwap_is_fresh_signal and base.state in ("fresh", "active"):
        if _bars_apart(avwap_evidence.as_of_bar_close_ms, base.bar_close_ms, timeframe_ms) <= event_alignment_bars:
            return "avwap_fresh"
    return None


def _opposes_strongly(evidence: DirectionalEvidence, base_sign: int, threshold: float) -> bool:
    return (
        evidence.quality != "unavailable"
        and evidence.direction != 0
        and evidence.direction != base_sign
        and evidence.confidence_100 >= threshold
    )


def _relative(component_direction: int, base_sign: int) -> int:
    if component_direction == 0:
        return 0
    return 1 if component_direction == base_sign else -1


def _component_score(evidence: DirectionalEvidence, base_sign: int) -> float:
    relative = _relative(evidence.direction, base_sign)
    return 50.0 * (1.0 + relative * evidence.confidence_100 / 100.0)


# ─────────────────────────────────────────────────────────────────────────
# Weighted scoring (spec §13.4)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ComponentContribution:
    name: str
    weight: float
    score: Optional[float]  # None -> omitted from both numerator and denominator (renormalized)


def compute_effective_score(
    base_score_100: float, base_weight: float, contributions: list[ComponentContribution],
) -> tuple[float, Optional[float]]:
    used = [c for c in contributions if c.score is not None]
    numerator = base_weight * base_score_100 + sum(c.weight * c.score for c in used)
    denominator = base_weight + sum(c.weight for c in used)
    effective = numerator / denominator if denominator > 0 else base_score_100

    suite_denominator = sum(c.weight for c in used)
    suite = (sum(c.weight * c.score for c in used) / suite_denominator) if suite_denominator > 0 else None
    return effective, suite


def compute_decision_id(
    *, user_id: str, engine_id: str, underlying: str, timeframe: str, bar_close_ms: int,
    direction: str, trigger: str, config_revision: int,
) -> str:
    payload = {
        "user_id": user_id, "engine_id": engine_id, "underlying": underlying, "timeframe": timeframe,
        "bar_close_ms": bar_close_ms, "direction": direction, "trigger": trigger, "config_revision": config_revision,
    }
    return "nav_" + canonical_json_hash(payload)[:24]


# ─────────────────────────────────────────────────────────────────────────
# Top-level fusion inputs + entry point
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FusionInputs:
    base: BaseSignalEvidence
    avwap: DirectionalEvidence
    avwap_grade: AvwapGradeLabel
    avwap_is_fresh_signal: bool
    volatility: DirectionalEvidence
    volatility_regime: Optional[Literal["EXPANSION", "COMPRESSION", "NEUTRAL"]]
    flow: DirectionalEvidence
    flow_required: bool
    flow_not_applicable: bool
    gamma: DirectionalEvidence
    gamma_required: bool
    range_impulse_supported: bool


def _build(
    *, base: BaseSignalEvidence, trigger: Optional[str], status: str, reasons: list[str],
    config_revision: int, model_versions: dict, generated_at_ms: int, activation_watermark_ms: int,
    avwap: Optional[DirectionalEvidence] = None, volatility: Optional[DirectionalEvidence] = None,
    flow: Optional[DirectionalEvidence] = None, gamma: Optional[DirectionalEvidence] = None,
    effective_score: Optional[float] = None, suite_score: Optional[float] = None,
) -> NavigatorDecision:
    trigger_value = trigger or "base_fresh"
    decision_id = compute_decision_id(
        user_id=base.user_id, engine_id=base.engine_id, underlying=base.underlying, timeframe=base.timeframe,
        bar_close_ms=base.bar_close_ms, direction=base.direction, trigger=trigger_value, config_revision=config_revision,
    )
    valid_reasons = sorted({r for r in reasons if r in ReasonCode.__args__}) or ["OK"]
    return NavigatorDecision(
        decision_id=decision_id, config_revision=config_revision, model_versions=model_versions,
        generated_at_ms=generated_at_ms, bar_close_ms=base.bar_close_ms, activation_watermark_ms=activation_watermark_ms,
        base_signal_id=base.signal_id, trigger=trigger_value, direction=base.direction, status=status,
        base_score=base.score_100, suite_score=suite_score, effective_score=effective_score,
        execution_eligible=status in ("CONFIRMED", "HIGH_CONVICTION"),
        data_quality="unavailable" if status == "NO_DATA" else "ok",
        reason_codes=valid_reasons, avwap=avwap, volatility=volatility, option_flow=flow, gamma=gamma,
    )


def fuse(inputs: FusionInputs, *, config, activation_watermark_ms: int, generated_at_ms: int, config_revision: int, model_versions: dict) -> NavigatorDecision:
    base = inputs.base
    base_sign = 1 if base.direction == "long" else -1
    timeframe_ms = 60 * 60 * 1000  # v1: base_timeframe is always "60minute"

    common = dict(
        base=base, config_revision=config_revision, model_versions=model_versions,
        generated_at_ms=generated_at_ms, activation_watermark_ms=activation_watermark_ms,
    )

    # ── required-input NO_DATA gate ──
    if inputs.avwap.quality == "unavailable":
        return _build(**common, trigger=None, status="NO_DATA", reasons=inputs.avwap.reason_codes, avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)
    if inputs.volatility.quality == "unavailable":
        return _build(**common, trigger=None, status="NO_DATA", reasons=inputs.volatility.reason_codes, avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)
    if inputs.flow_required and not inputs.flow_not_applicable and inputs.flow.quality == "unavailable":
        return _build(**common, trigger=None, status="NO_DATA", reasons=inputs.flow.reason_codes, avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)
    if inputs.gamma_required and inputs.gamma.quality == "unavailable":
        return _build(**common, trigger=None, status="NO_DATA", reasons=inputs.gamma.reason_codes, avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)

    # ── trigger ──
    trigger = determine_trigger(base, inputs.avwap, inputs.avwap_is_fresh_signal, config.event_alignment_bars, timeframe_ms)

    # ── activation watermark ──
    if trigger is not None:
        trigger_bar_close_ms = base.bar_close_ms if trigger == "base_fresh" else inputs.avwap.as_of_bar_close_ms
        if trigger_bar_close_ms < activation_watermark_ms:
            return _build(**common, trigger=trigger, status="WAIT", reasons=["ACTIVATION_WATERMARK"], avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)

    # ── compression forces WAIT ──
    if inputs.volatility_regime == "COMPRESSION":
        return _build(**common, trigger=trigger, status="WAIT", reasons=["COMPRESSION_NO_TREND"], avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)

    # ── no fresh trigger -> WATCH ──
    if trigger is None:
        return _build(**common, trigger=None, status="WATCH", reasons=["NO_FRESH_TRIGGER"], avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)

    # ── strong opposition -> CONFLICT (gamma disagreement never counts here) ──
    if (
        _opposes_strongly(inputs.avwap, base_sign, config.fusion.strong_conflict_confidence)
        or _opposes_strongly(inputs.volatility, base_sign, config.fusion.strong_conflict_confidence)
        or _opposes_strongly(inputs.flow, base_sign, config.fusion.strong_conflict_confidence)
    ):
        return _build(**common, trigger=trigger, status="CONFLICT", reasons=["STRONG_OPPOSING_EVIDENCE"], avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma)

    # ── scoring ──
    reason_codes: list[str] = []
    avwap_score = _component_score(inputs.avwap, base_sign)
    volatility_score = _component_score(inputs.volatility, base_sign)

    if inputs.flow_not_applicable:
        flow_contribution = ComponentContribution("flow", config.fusion.flow_weight, None)
        reason_codes.append("COMPONENT_NOT_APPLICABLE")
    elif inputs.flow.quality == "unavailable":
        flow_contribution = ComponentContribution("flow", config.fusion.flow_weight, 50.0)
    else:
        flow_contribution = ComponentContribution("flow", config.fusion.flow_weight, _component_score(inputs.flow, base_sign))

    if inputs.gamma.quality == "unavailable":
        gamma_contribution = ComponentContribution("gamma", config.fusion.gamma_weight, 50.0)
        reason_codes.append("GAMMA_UNAVAILABLE_OPTIONAL")
    else:
        gamma_contribution = ComponentContribution("gamma", config.fusion.gamma_weight, _component_score(inputs.gamma, base_sign))

    contributions = [
        ComponentContribution("avwap", config.fusion.avwap_weight, avwap_score),
        ComponentContribution("volatility", config.fusion.volatility_weight, volatility_score),
        flow_contribution, gamma_contribution,
    ]
    effective_score, suite_score = compute_effective_score(base.score_100, config.fusion.base_weight, contributions)

    grade_ok = _grade_meets_min(inputs.avwap_grade, config.fusion.min_avwap_grade)
    high_conviction_ok = (
        _grade_meets_min(inputs.avwap_grade, "A+")
        and inputs.volatility_regime == "EXPANSION"
        and inputs.flow.quality != "unavailable" and inputs.flow.direction == base_sign
        and inputs.range_impulse_supported
    )

    if effective_score >= config.fusion.high_conviction_score_min and high_conviction_ok:
        status = "HIGH_CONVICTION"
    elif effective_score >= config.fusion.confirmed_score_min and grade_ok:
        status = "CONFIRMED"
    else:
        status = "WATCH"
        reason_codes.append("SCORE_BELOW_THRESHOLD")

    return _build(
        **common, trigger=trigger, status=status, reasons=reason_codes or ["OK"],
        avwap=inputs.avwap, volatility=inputs.volatility, flow=inputs.flow, gamma=inputs.gamma,
        effective_score=effective_score, suite_score=suite_score,
    )
