from __future__ import annotations

import pytest

from app.engines.navigator.fusion import (
    ComponentContribution,
    FusionInputs,
    compute_decision_id,
    compute_effective_score,
    determine_trigger,
    fuse,
)
from app.engines.navigator.schemas import BaseSignalEvidence, DirectionalEvidence, NavigatorConfigModel

_BAR_MS = 1_753_000_000_000
_HOUR_MS = 3_600_000


def _base(**overrides):
    base = dict(
        signal_id="s1", user_id="u1", underlying="NIFTY 50", exchange="NFO", instrument_token=1,
        timeframe="60minute", bar_open_ms=_BAR_MS - _HOUR_MS, bar_close_ms=_BAR_MS, observed_at_ms=_BAR_MS + 5000,
        direction="long", state="fresh", score_100=85.0, source="spot", strategy="triple_supertrend",
        config_revision="abc", raw_payload_hash="hash",
    )
    base.update(overrides)
    return BaseSignalEvidence(**base)


def _evidence(component, **overrides):
    base = dict(
        component=component, as_of_bar_close_ms=_BAR_MS, observed_at_ms=_BAR_MS + 5000,
        direction=1, confidence_100=80.0, quality="ok", reason_codes=["OK"], diagnostics={},
    )
    base.update(overrides)
    return DirectionalEvidence(**base)


def _inputs(**overrides):
    defaults = dict(
        base=_base(), avwap=_evidence("avwap"), avwap_grade="A", avwap_is_fresh_signal=True,
        volatility=_evidence("volatility"), volatility_regime="NEUTRAL",
        flow=_evidence("option_flow"), flow_required=True, flow_not_applicable=False,
        gamma=_evidence("gamma", direction=0, confidence_100=0.0), gamma_required=False,
        range_impulse_supported=False,
    )
    defaults.update(overrides)
    return FusionInputs(**defaults)


def _fuse(inputs, **cfg_overrides):
    cfg = NavigatorConfigModel.default_for(["NIFTY 50"])
    if cfg_overrides:
        cfg = cfg.model_copy(update=cfg_overrides)
    return fuse(inputs, config=cfg, activation_watermark_ms=0, generated_at_ms=_BAR_MS + 5000, config_revision=1, model_versions={"fusion": "v1"})


class TestHardGateTruthTable:
    def test_required_avwap_unavailable_is_no_data(self):
        inputs = _inputs(avwap=_evidence("avwap", quality="unavailable", direction=0, confidence_100=0.0, reason_codes=["AVWAP_WARMING_UP"]))
        decision = _fuse(inputs)
        assert decision.status == "NO_DATA"
        assert decision.execution_eligible is False
        assert decision.effective_score is None

    def test_required_volatility_unavailable_is_no_data(self):
        inputs = _inputs(volatility=_evidence("volatility", quality="unavailable", direction=0, confidence_100=0.0, reason_codes=["VOL_WARMING_UP"]))
        decision = _fuse(inputs)
        assert decision.status == "NO_DATA"

    def test_required_flow_unavailable_is_no_data(self):
        inputs = _inputs(flow=_evidence("option_flow", quality="unavailable", direction=0, confidence_100=0.0, reason_codes=["FLOW_WARMING_UP"]), flow_required=True, flow_not_applicable=False)
        decision = _fuse(inputs)
        assert decision.status == "NO_DATA"

    def test_flow_not_applicable_does_not_trigger_no_data(self):
        inputs = _inputs(flow=_evidence("option_flow", quality="unavailable", direction=0, confidence_100=0.0, reason_codes=["CHAIN_UNAVAILABLE"]), flow_required=True, flow_not_applicable=True)
        decision = _fuse(inputs)
        assert decision.status != "NO_DATA"
        assert "COMPONENT_NOT_APPLICABLE" in decision.reason_codes

    def test_gamma_unavailable_never_causes_no_data_by_default(self):
        inputs = _inputs(gamma=_evidence("gamma", quality="unavailable", direction=0, confidence_100=0.0, reason_codes=["GAMMA_WARMING_UP"]), gamma_required=False)
        decision = _fuse(inputs)
        assert decision.status != "NO_DATA"
        assert "GAMMA_UNAVAILABLE_OPTIONAL" in decision.reason_codes

    def test_gamma_required_and_unavailable_is_no_data(self):
        inputs = _inputs(gamma=_evidence("gamma", quality="unavailable", direction=0, confidence_100=0.0, reason_codes=["GAMMA_WARMING_UP"]), gamma_required=True)
        decision = _fuse(inputs)
        assert decision.status == "NO_DATA"

    def test_activation_watermark_excludes_trigger(self):
        inputs = _inputs()
        cfg = NavigatorConfigModel.default_for(["NIFTY 50"])
        decision = fuse(inputs, config=cfg, activation_watermark_ms=_BAR_MS + 999_999_999, generated_at_ms=_BAR_MS + 5000, config_revision=1, model_versions={})
        assert decision.status == "WAIT"
        assert "ACTIVATION_WATERMARK" in decision.reason_codes
        assert decision.execution_eligible is False

    def test_compression_forces_wait(self):
        inputs = _inputs(volatility_regime="COMPRESSION")
        decision = _fuse(inputs)
        assert decision.status == "WAIT"
        assert "COMPRESSION_NO_TREND" in decision.reason_codes

    def test_no_fresh_trigger_is_watch(self):
        stale_base = _base(state="active")  # not fresh
        inputs = _inputs(base=stale_base, avwap_is_fresh_signal=False)
        decision = _fuse(inputs)
        assert decision.status == "WATCH"
        assert "NO_FRESH_TRIGGER" in decision.reason_codes
        assert decision.execution_eligible is False

    def test_no_fresh_trigger_not_required_falls_through_to_scoring(self):
        """`fusion.require_fresh_trigger=False` means the user opted OUT of
        the fresh-trigger requirement — the exact same no-trigger inputs
        that force WATCH by default must instead reach real scoring."""
        stale_base = _base(state="active")  # not fresh
        inputs = _inputs(
            base=stale_base, avwap_is_fresh_signal=False,
            avwap=_evidence("avwap", direction=1, confidence_100=90.0), avwap_grade="A",
            volatility=_evidence("volatility", direction=1, confidence_100=80.0),
            flow=_evidence("option_flow", direction=1, confidence_100=70.0),
        )
        cfg = NavigatorConfigModel.default_for(["NIFTY 50"])
        cfg = cfg.model_copy(update={"fusion": cfg.fusion.model_copy(update={"require_fresh_trigger": False})})
        decision = fuse(inputs, config=cfg, activation_watermark_ms=0, generated_at_ms=_BAR_MS + 5000, config_revision=1, model_versions={"fusion": "v1"})
        assert decision.status in ("CONFIRMED", "HIGH_CONVICTION")
        assert "NO_FRESH_TRIGGER" not in decision.reason_codes

    def test_strong_avwap_opposition_is_conflict(self):
        inputs = _inputs(avwap=_evidence("avwap", direction=-1, confidence_100=90.0))
        decision = _fuse(inputs)
        assert decision.status == "CONFLICT"
        assert "STRONG_OPPOSING_EVIDENCE" in decision.reason_codes
        assert decision.execution_eligible is False

    def test_strong_volatility_opposition_is_conflict(self):
        inputs = _inputs(volatility=_evidence("volatility", direction=-1, confidence_100=95.0))
        decision = _fuse(inputs)
        assert decision.status == "CONFLICT"

    def test_strong_flow_opposition_is_conflict(self):
        inputs = _inputs(flow=_evidence("option_flow", direction=-1, confidence_100=95.0))
        decision = _fuse(inputs)
        assert decision.status == "CONFLICT"

    def test_weak_opposition_does_not_conflict(self):
        # opposes but below strong_conflict_confidence threshold (default 70)
        inputs = _inputs(avwap=_evidence("avwap", direction=-1, confidence_100=40.0))
        decision = _fuse(inputs)
        assert decision.status != "CONFLICT"

    def test_gamma_opposition_alone_cannot_create_conflict(self):
        inputs = _inputs(gamma=_evidence("gamma", direction=-1, confidence_100=99.0))
        decision = _fuse(inputs)
        assert decision.status != "CONFLICT"

    def test_aligned_evidence_confirms(self):
        inputs = _inputs(
            avwap=_evidence("avwap", direction=1, confidence_100=90.0), avwap_grade="A",
            volatility=_evidence("volatility", direction=1, confidence_100=80.0),
            flow=_evidence("option_flow", direction=1, confidence_100=70.0),
        )
        decision = _fuse(inputs)
        assert decision.status in ("CONFIRMED", "HIGH_CONVICTION")
        assert decision.execution_eligible is True

    def test_high_conviction_requires_all_prerequisites(self):
        inputs = _inputs(
            avwap=_evidence("avwap", direction=1, confidence_100=95.0), avwap_grade="A+",
            volatility=_evidence("volatility", direction=1, confidence_100=95.0), volatility_regime="EXPANSION",
            flow=_evidence("option_flow", direction=1, confidence_100=95.0),
            gamma=_evidence("gamma", direction=1, confidence_100=90.0),
            range_impulse_supported=True,
        )
        decision = _fuse(inputs)
        assert decision.status == "HIGH_CONVICTION"
        assert decision.execution_eligible is True

    def test_high_conviction_downgrades_to_confirmed_without_range_impulse(self):
        inputs = _inputs(
            avwap=_evidence("avwap", direction=1, confidence_100=95.0), avwap_grade="A+",
            volatility=_evidence("volatility", direction=1, confidence_100=95.0), volatility_regime="EXPANSION",
            flow=_evidence("option_flow", direction=1, confidence_100=95.0),
            range_impulse_supported=False,  # missing prerequisite
        )
        decision = _fuse(inputs)
        assert decision.status != "HIGH_CONVICTION"

    def test_below_b_grade_avwap_cannot_confirm_by_default(self):
        inputs = _inputs(
            avwap=_evidence("avwap", direction=1, confidence_100=90.0), avwap_grade="none",
            volatility=_evidence("volatility", direction=1, confidence_100=90.0),
            flow=_evidence("option_flow", direction=1, confidence_100=90.0),
        )
        decision = _fuse(inputs)
        assert decision.status == "WATCH"
        assert "SCORE_BELOW_THRESHOLD" in decision.reason_codes

    def test_low_score_is_watch_not_confirmed(self):
        inputs = _inputs(
            avwap=_evidence("avwap", direction=0, confidence_100=0.0),
            volatility=_evidence("volatility", direction=0, confidence_100=0.0),
            flow=_evidence("option_flow", direction=0, confidence_100=0.0),
        )
        decision = _fuse(inputs)
        assert decision.status == "WATCH"


class TestTriggerRule:
    def test_base_fresh_with_initialized_avwap(self):
        base = _base(state="fresh")
        avwap_ev = _evidence("avwap", quality="ok")
        trigger = determine_trigger(base, avwap_ev, avwap_is_fresh_signal=False, event_alignment_bars=2, timeframe_ms=_HOUR_MS)
        assert trigger == "base_fresh"

    def test_avwap_fresh_with_active_base_within_alignment(self):
        base = _base(state="active", bar_close_ms=_BAR_MS)
        avwap_ev = _evidence("avwap", quality="ok", as_of_bar_close_ms=_BAR_MS + _HOUR_MS, observed_at_ms=_BAR_MS + _HOUR_MS + 5000)
        trigger = determine_trigger(base, avwap_ev, avwap_is_fresh_signal=True, event_alignment_bars=2, timeframe_ms=_HOUR_MS)
        assert trigger == "avwap_fresh"

    def test_avwap_fresh_too_far_from_base_is_no_trigger(self):
        base = _base(state="active", bar_close_ms=_BAR_MS)
        avwap_ev = _evidence("avwap", quality="ok", as_of_bar_close_ms=_BAR_MS + 10 * _HOUR_MS, observed_at_ms=_BAR_MS + 10 * _HOUR_MS + 5000)
        trigger = determine_trigger(base, avwap_ev, avwap_is_fresh_signal=True, event_alignment_bars=2, timeframe_ms=_HOUR_MS)
        assert trigger is None

    def test_neither_fresh_is_no_trigger(self):
        base = _base(state="active")
        avwap_ev = _evidence("avwap", quality="ok")
        trigger = determine_trigger(base, avwap_ev, avwap_is_fresh_signal=False, event_alignment_bars=2, timeframe_ms=_HOUR_MS)
        assert trigger is None


class TestScoreFormula:
    def test_fully_aligned_confidence_100_gives_component_score_100(self):
        contributions = [ComponentContribution("avwap", 25.0, 100.0)]
        effective, suite = compute_effective_score(100.0, 35.0, contributions)
        # base=100 (weight 35) + avwap component=100 (weight 25); other implicit
        assert effective == pytest.approx(100.0)

    def test_neutral_evidence_gives_fifty(self):
        contributions = [ComponentContribution("avwap", 25.0, 50.0)]
        effective, suite = compute_effective_score(100.0, 75.0, contributions)
        assert effective == pytest.approx(100.0 * 0.75 + 50.0 * 0.25)

    def test_omitted_component_is_renormalized_out(self):
        contributions = [ComponentContribution("flow", 15.0, None)]
        effective, suite = compute_effective_score(80.0, 35.0, contributions)
        assert effective == pytest.approx(80.0)  # only base remains after renormalization
        assert suite is None

    def test_suite_score_excludes_base(self):
        contributions = [ComponentContribution("avwap", 25.0, 90.0), ComponentContribution("volatility", 20.0, 60.0)]
        effective, suite = compute_effective_score(100.0, 35.0, contributions)
        expected_suite = (25.0 * 90.0 + 20.0 * 60.0) / (25.0 + 20.0)
        assert suite == pytest.approx(expected_suite)


class TestDecisionIdDeterminism:
    def test_identical_inputs_produce_identical_id(self):
        kwargs = dict(user_id="u1", engine_id="kite_triple_supertrend", underlying="NIFTY 50", timeframe="60minute", bar_close_ms=_BAR_MS, direction="long", trigger="base_fresh", config_revision=1)
        assert compute_decision_id(**kwargs) == compute_decision_id(**kwargs)

    def test_different_bar_close_produces_different_id(self):
        id1 = compute_decision_id(user_id="u1", engine_id="e", underlying="NIFTY", timeframe="60minute", bar_close_ms=1, direction="long", trigger="base_fresh", config_revision=1)
        id2 = compute_decision_id(user_id="u1", engine_id="e", underlying="NIFTY", timeframe="60minute", bar_close_ms=2, direction="long", trigger="base_fresh", config_revision=1)
        assert id1 != id2

    def test_replay_is_idempotent_end_to_end(self):
        inputs = _inputs()
        d1 = _fuse(inputs)
        d2 = _fuse(inputs)
        assert d1.decision_id == d2.decision_id
        assert d1.status == d2.status
        assert d1.effective_score == d2.effective_score


class TestGateEligibilityByMode:
    def test_shadow_and_advisory_never_set_execution_eligible_from_status_alone_without_confirmation(self):
        # fusion itself only reflects status; mode/readiness gating happens
        # in the service layer (Phase 5) — this documents that boundary.
        inputs = _inputs(
            avwap=_evidence("avwap", direction=1, confidence_100=95.0), avwap_grade="A",
            volatility=_evidence("volatility", direction=1, confidence_100=90.0),
            flow=_evidence("option_flow", direction=1, confidence_100=90.0),
        )
        decision = _fuse(inputs)
        assert decision.status == "CONFIRMED"
        assert decision.execution_eligible is True  # candidate-eligible; service layer still must gate on mode/readiness
