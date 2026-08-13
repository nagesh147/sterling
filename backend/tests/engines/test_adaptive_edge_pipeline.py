from app.engines.adaptive_edge.edge import EdgeAssessment
from app.engines.adaptive_edge.economic import evaluate_economics
from app.engines.adaptive_edge.feature_engine import FeatureInput, InstrumentContext, build_feature_snapshot
import pytest


def _snapshot_kwargs():
    return dict(
        snapshot_id="snap-1",
        strategy_version="strategy-1",
        feature_set_version="features-1",
        observation_cutoff_time="2026-08-11T10:00:00+00:00",
        decision_time="2026-08-11T10:00:00+00:00",
        instrument_context=InstrumentContext("NIFTY"),
    )


def test_future_feature_is_rejected():
    with pytest.raises(ValueError, match="lookahead detected"):
        build_feature_snapshot(
            **_snapshot_kwargs(),
            inputs=[FeatureInput("x", 1.0, "2026-08-11T10:01:00+00:00")],
        )


def test_timestamp_comparison_is_semantic_not_lexical():
    with pytest.raises(ValueError, match="lookahead detected"):
        build_feature_snapshot(
            **_snapshot_kwargs(),
            inputs=[FeatureInput("x", 1.0, "2026-08-11T10:01:00+05:30")],
        )


def test_snapshot_mappings_are_immutable():
    snapshot = build_feature_snapshot(
        **_snapshot_kwargs(),
        inputs=[FeatureInput("x", 1.0, "2026-08-11T09:59:00+00:00")],
    )
    with pytest.raises(TypeError):
        snapshot.values["x"] = 2.0


def test_expected_net_value_is_gross_minus_cost():
    edge = EdgeAssessment("o1", 0.8, 0.9, 100.0, "F-102", "1.0", {})
    result = evaluate_economics(edge, execution_cost=15.0)
    assert result.expected_net_value == 85.0
    assert result.eligible is True


def test_higher_execution_cost_cannot_improve_net_value():
    edge = EdgeAssessment("o1", 0.8, 0.9, 100.0, "F-102", "1.0", {})
    a = evaluate_economics(edge, execution_cost=10.0)
    b = evaluate_economics(edge, execution_cost=20.0)
    assert b.expected_net_value <= a.expected_net_value


def test_missing_gross_value_fails_economic_gate():
    edge = EdgeAssessment("o1", 0.8, 0.9, None, "F-102", "1.0", {})
    result = evaluate_economics(edge, execution_cost=0.0)
    assert result.eligible is False
    assert result.reason == "missing_expected_gross_value"
