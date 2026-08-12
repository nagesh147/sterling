"""A42 economic-value and decision-utility boundary primitives.

Only structural relationships are implemented. Payoffs, probability semantics,
execution costs, risk measures, utility functions, and thresholds must be
supplied explicitly by an upstream versioned contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Sequence


class EconomicDecisionError(ValueError):
    pass


class DecisionStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NO_ACTION = "NO_ACTION"


class RejectionReason(str, Enum):
    PREDICTION_INVALID = "PREDICTION_INVALID"
    ECONOMIC_VALUE_INSUFFICIENT = "ECONOMIC_VALUE_INSUFFICIENT"
    RISK_CONSTRAINT = "RISK_CONSTRAINT"
    EXECUTION_CONSTRAINT = "EXECUTION_CONSTRAINT"
    CONTRACT_CONSTRAINT = "CONTRACT_CONSTRAINT"
    DATA_INVALID = "DATA_INVALID"
    POLICY_DISABLED = "POLICY_DISABLED"
    OTHER_EXPLICIT_FAILURE = "OTHER_EXPLICIT_FAILURE"


@dataclass(frozen=True)
class OutcomeValue:
    outcome_id: str
    probability: float
    gross_value: float

    def __post_init__(self) -> None:
        if not self.outcome_id.strip():
            raise EconomicDecisionError("outcome_id must not be empty")
        if not isfinite(self.probability) or not 0.0 <= self.probability <= 1.0:
            raise EconomicDecisionError("outcome probability must be in [0, 1]")
        if not isfinite(self.gross_value):
            raise EconomicDecisionError("gross_value must be finite")


@dataclass(frozen=True)
class ExecutionAssessment:
    assessment_id: str
    expected_cost: float
    available_at: datetime
    feasible: bool = True

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise EconomicDecisionError("execution assessment id must not be empty")
        if not isfinite(self.expected_cost) or self.expected_cost < 0:
            raise EconomicDecisionError("expected execution cost must be finite and non-negative")
        _require_aware(self.available_at, "execution availability time")


@dataclass(frozen=True)
class RiskAssessment:
    assessment_id: str
    risk_value: float
    risk_limit: float

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise EconomicDecisionError("risk assessment id must not be empty")
        if not isfinite(self.risk_value) or not isfinite(self.risk_limit):
            raise EconomicDecisionError("risk values must be finite")
        if self.risk_limit < 0:
            raise EconomicDecisionError("risk limit must be non-negative")

    @property
    def within_limit(self) -> bool:
        return self.risk_value <= self.risk_limit


@dataclass(frozen=True)
class EconomicAssessment:
    assessment_id: str
    gross_expected_value: float
    execution_cost: float
    net_expected_value: float
    decision_time: datetime
    execution_assessment_id: str
    risk_assessment_id: str

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise EconomicDecisionError("economic assessment id must not be empty")
        if not all(isfinite(value) for value in (self.gross_expected_value, self.execution_cost, self.net_expected_value)):
            raise EconomicDecisionError("economic values must be finite")
        if abs(self.net_expected_value - (self.gross_expected_value - self.execution_cost)) > 1e-12:
            raise EconomicDecisionError("net expected value must equal gross value minus execution cost")
        _require_aware(self.decision_time, "decision time")


@dataclass(frozen=True)
class DecisionAssessment:
    decision_id: str
    prediction_id: str
    feature_snapshot_id: str
    economic_assessment_id: str
    risk_assessment_id: str
    execution_assessment_id: str
    policy_version: str
    decision_time: datetime
    status: DecisionStatus
    reason: RejectionReason | None

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "prediction_id",
            "feature_snapshot_id",
            "economic_assessment_id",
            "risk_assessment_id",
            "execution_assessment_id",
            "policy_version",
        ):
            if not getattr(self, name).strip():
                raise EconomicDecisionError(f"{name} must not be empty")
        _require_aware(self.decision_time, "decision time")
        if self.status is DecisionStatus.ELIGIBLE and self.reason is not None:
            raise EconomicDecisionError("eligible decision cannot have a rejection reason")
        if self.status is DecisionStatus.NO_ACTION and self.reason is None:
            raise EconomicDecisionError("no-action decision requires an explicit rejection reason")


def expected_gross_value(outcomes: Sequence[OutcomeValue]) -> float:
    """Compute E[G|X] from an explicitly supplied discrete outcome distribution."""
    if not outcomes:
        raise EconomicDecisionError("at least one outcome is required")
    total_probability = sum(item.probability for item in outcomes)
    if abs(total_probability - 1.0) > 1e-12:
        raise EconomicDecisionError("outcome probabilities must sum to one")
    return sum(item.probability * item.gross_value for item in outcomes)


def assess_economic_value(
    *,
    assessment_id: str,
    outcomes: Sequence[OutcomeValue],
    execution: ExecutionAssessment,
    risk: RiskAssessment,
    decision_time: datetime,
) -> EconomicAssessment:
    """Apply only the structural gross-minus-cost relationship."""
    _require_aware(decision_time, "decision time")
    if execution.available_at > decision_time:
        raise EconomicDecisionError("execution cost is not causally available at decision time")
    gross = expected_gross_value(outcomes)
    net = gross - execution.expected_cost
    return EconomicAssessment(
        assessment_id=assessment_id,
        gross_expected_value=gross,
        execution_cost=execution.expected_cost,
        net_expected_value=net,
        decision_time=decision_time,
        execution_assessment_id=execution.assessment_id,
        risk_assessment_id=risk.assessment_id,
    )


def make_decision_assessment(
    *,
    decision_id: str,
    prediction_id: str,
    feature_snapshot_id: str,
    economic: EconomicAssessment,
    risk: RiskAssessment,
    execution: ExecutionAssessment,
    policy_version: str,
    decision_time: datetime,
    minimum_net_value: float | None = None,
) -> DecisionAssessment:
    """Produce eligibility only from explicitly supplied policy constraints."""
    _require_aware(decision_time, "decision time")
    if economic.decision_time != decision_time:
        raise EconomicDecisionError("economic assessment time does not match decision time")
    if not execution.feasible:
        return _no_action(decision_id, prediction_id, feature_snapshot_id, economic, risk, execution, policy_version, decision_time, RejectionReason.EXECUTION_CONSTRAINT)
    if not risk.within_limit:
        return _no_action(decision_id, prediction_id, feature_snapshot_id, economic, risk, execution, policy_version, decision_time, RejectionReason.RISK_CONSTRAINT)
    if minimum_net_value is not None and economic.net_expected_value < minimum_net_value:
        return _no_action(decision_id, prediction_id, feature_snapshot_id, economic, risk, execution, policy_version, decision_time, RejectionReason.ECONOMIC_VALUE_INSUFFICIENT)
    return DecisionAssessment(
        decision_id=decision_id,
        prediction_id=prediction_id,
        feature_snapshot_id=feature_snapshot_id,
        economic_assessment_id=economic.assessment_id,
        risk_assessment_id=risk.assessment_id,
        execution_assessment_id=execution.assessment_id,
        policy_version=policy_version,
        decision_time=decision_time,
        status=DecisionStatus.ELIGIBLE,
        reason=None,
    )


def _no_action(decision_id, prediction_id, feature_snapshot_id, economic, risk, execution, policy_version, decision_time, reason):
    return DecisionAssessment(
        decision_id=decision_id,
        prediction_id=prediction_id,
        feature_snapshot_id=feature_snapshot_id,
        economic_assessment_id=economic.assessment_id,
        risk_assessment_id=risk.assessment_id,
        execution_assessment_id=execution.assessment_id,
        policy_version=policy_version,
        decision_time=decision_time,
        status=DecisionStatus.NO_ACTION,
        reason=reason,
    )


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EconomicDecisionError(f"{name} must be timezone-aware")
