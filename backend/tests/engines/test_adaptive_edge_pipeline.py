from dataclasses import dataclass

import pytest

from app.engines.adaptive_edge.edge import EdgeAssessment, StrategyFormulaLockedError
from app.engines.adaptive_edge.economic import evaluate_economics
from app.engines.adaptive_edge.feature_engine import FeatureInput, build_feature_snapshot


def test_future_feature_is_rejected():
    with pytest.raises(ValueError, match="lookahead detected"):
        build_feature_snapshot(
            observation_time="2026-08-11T10:00:00",
            inputs=[FeatureInput("x", 1.0, "2026-08-11T10:01:00")],
            decision_time="2026-08-11T10:00:00",
        )


def test_expected_net_value_is_gross_minus_cost():
    edge = EdgeAssessment("o1", 0.8, 0.9, 100.0, "MS-31/66", "1.0", {})
    result = evaluate_economics(edge, execution_cost=15.0)
    assert result.expected_net_value == 85.0


def test_higher_execution_cost_cannot_improve_net_value():
    edge = EdgeAssessment("o1", 0.8, 0.9, 100.0, "MS-31/66", "1.0", {})
    a = evaluate_economics(edge, execution_cost=10.0)
    b = evaluate_economics(edge, execution_cost=20.0)
    assert b.expected_net_value <= a.expected_net_value


def test_missing_gross_value_is_not_silently_converted_to_zero():
    edge = EdgeAssessment("o1", 0.8, 0.9, None, "MS-31/66", "1.0", {})
    with pytest.raises(ValueError, match="expected gross value is required"):
        evaluate_economics(edge, execution_cost=0.0)
