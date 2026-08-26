import pytest

from app.engines.adaptive_edge.edge import EdgeAssessment
from app.engines.adaptive_edge.economic import evaluate_economics


def edge(gross):
    return EdgeAssessment(
        opportunity_id="o1",
        score=0.0,
        confidence=None,
        expected_gross_value=gross,
        formula_id="MS-test",
        formula_version="1.0",
        # EdgeAssessment carries the inputs its score came from, so a score can
        # be traced back rather than taken on faith.
        inputs={},
    )


def test_zero_net_value_is_not_eligible():
    result = evaluate_economics(edge(10.0), execution_cost=10.0)
    assert not result.eligible
    # Formula ids come from the registry: F-004. "MS-31/66" is a master-spec
    # section reference and appears nowhere else in the engine or its tests.
    assert result.formula_id == "F-004"


def test_negative_execution_cost_is_rejected():
    with pytest.raises(ValueError):
        evaluate_economics(edge(10.0), execution_cost=-1.0)
