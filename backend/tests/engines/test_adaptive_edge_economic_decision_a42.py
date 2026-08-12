from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.economic_decision import (
    DecisionStatus,
    EconomicDecisionError,
    ExecutionAssessment,
    OutcomeValue,
    RejectionReason,
    RiskAssessment,
    assess_economic_value,
    expected_gross_value,
    make_decision_assessment,
)

DT = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def execution(cost=2.0, feasible=True):
    return ExecutionAssessment("exec-1", cost, DT, feasible)


def risk(value=3.0, limit=5.0):
    return RiskAssessment("risk-1", value, limit)


def economic(net_cost=2.0):
    return assess_economic_value(
        assessment_id="econ-1",
        outcomes=(
            OutcomeValue("win", 0.6, 10.0),
            OutcomeValue("loss", 0.4, -5.0),
        ),
        execution=execution(net_cost),
        risk=risk(),
        decision_time=DT,
    )


def test_expected_gross_value_uses_supplied_outcome_distribution():
    assert expected_gross_value(
        (OutcomeValue("a", 0.25, 8.0), OutcomeValue("b", 0.75, 4.0))
    ) == pytest.approx(5.0)


def test_probability_mass_must_sum_to_one():
    with pytest.raises(EconomicDecisionError):
        expected_gross_value((OutcomeValue("a", 0.5, 10.0),))


def test_net_value_is_gross_minus_ex_ante_cost():
    assessment = economic(2.0)
    assert assessment.gross_expected_value == pytest.approx(4.0)
    assert assessment.net_expected_value == pytest.approx(2.0)


def test_future_execution_cost_is_rejected():
    future = ExecutionAssessment("exec-1", 2.0, datetime(2026, 8, 11, 10, 1, tzinfo=timezone.utc))
    with pytest.raises(EconomicDecisionError):
        assess_economic_value(
            assessment_id="econ-1",
            outcomes=(OutcomeValue("x", 1.0, 5.0),),
            execution=future,
            risk=risk(),
            decision_time=DT,
        )


def test_risk_constraint_fails_closed():
    result = make_decision_assessment(
        decision_id="decision-1",
        prediction_id="pred-1",
        feature_snapshot_id="snapshot-1",
        economic=economic(),
        risk=risk(value=6.0, limit=5.0),
        execution=execution(),
        policy_version="policy-1",
        decision_time=DT,
    )
    assert result.status is DecisionStatus.NO_ACTION
    assert result.reason is RejectionReason.RISK_CONSTRAINT


def test_execution_constraint_fails_closed():
    result = make_decision_assessment(
        decision_id="decision-1",
        prediction_id="pred-1",
        feature_snapshot_id="snapshot-1",
        economic=economic(),
        risk=risk(),
        execution=execution(feasible=False),
        policy_version="policy-1",
        decision_time=DT,
    )
    assert result.status is DecisionStatus.NO_ACTION
    assert result.reason is RejectionReason.EXECUTION_CONSTRAINT


def test_net_value_threshold_is_explicit_policy_input():
    result = make_decision_assessment(
        decision_id="decision-1",
        prediction_id="pred-1",
        feature_snapshot_id="snapshot-1",
        economic=economic(),
        risk=risk(),
        execution=execution(),
        policy_version="policy-1",
        decision_time=DT,
        minimum_net_value=3.0,
    )
    assert result.status is DecisionStatus.NO_ACTION
    assert result.reason is RejectionReason.ECONOMIC_VALUE_INSUFFICIENT


def test_eligible_result_has_no_rejection_reason():
    result = make_decision_assessment(
        decision_id="decision-1",
        prediction_id="pred-1",
        feature_snapshot_id="snapshot-1",
        economic=economic(),
        risk=risk(),
        execution=execution(),
        policy_version="policy-1",
        decision_time=DT,
    )
    assert result.status is DecisionStatus.ELIGIBLE
    assert result.reason is None
