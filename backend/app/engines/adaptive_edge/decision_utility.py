"""A42 structural economic-decision boundary.

This module records economic inputs and explicit eligibility outcomes. It does
not invent payoff distributions, utility functions, thresholds, risk formulas,
or execution-cost models.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite


class DecisionUtilityError(ValueError):
    """Raised when an A42 structural invariant is violated."""


class DecisionFailure(str, Enum):
    PREDICTION_INVALID = "PREDICTION_INVALID"
    ECONOMIC_VALUE_INSUFFICIENT = "ECONOMIC_VALUE_INSUFFICIENT"
    RISK_CONSTRAINT = "RISK_CONSTRAINT"
    EXECUTION_CONSTRAINT = "EXECUTION_CONSTRAINT"
    CONTRACT_CONSTRAINT = "CONTRACT_CONSTRAINT"
    DATA_INVALID = "DATA_INVALID"
    POLICY_DISABLED = "POLICY_DISABLED"
    OTHER_EXPLICIT_FAILURE = "OTHER_EXPLICIT_FAILURE"


@dataclass(frozen=True)
class EconomicContext:
    assessment_id: str
    gross_value: float | None
    expected_execution_cost: float | None
    risk_assessment_id: str | None
    execution_assessment_id: str | None

    def __post_init__(self) -> None:
        if not self.assessment_id.strip():
            raise DecisionUtilityError("assessment_id must not be empty")
        for name, value in (("gross_value", self.gross_value), ("expected_execution_cost", self.expected_execution_cost)):
            if value is not None and not isfinite(value):
                raise DecisionUtilityError(f"{name} must be finite when supplied")


@dataclass(frozen=True)
class DecisionAssessment:
    decision_id: str
    prediction_id: str
    feature_snapshot_id: str
    economic_assessment_id: str
    risk_assessment_id: str | None
    execution_assessment_id: str | None
    policy_version: str
    decision_time: datetime
    eligible: bool
    failure: DecisionFailure | None = None

    def __post_init__(self) -> None:
        for name in ("decision_id", "prediction_id", "feature_snapshot_id", "economic_assessment_id", "policy_version"):
            if not getattr(self, name).strip():
                raise DecisionUtilityError(f"{name} must not be empty")
        if self.decision_time.tzinfo is None or self.decision_time.utcoffset() is None:
            raise DecisionUtilityError("decision_time must be timezone-aware")
        if self.eligible and self.failure is not None:
            raise DecisionUtilityError("eligible decision cannot carry a failure reason")
        if not self.eligible and self.failure is None:
            raise DecisionUtilityError("ineligible decision requires an explicit failure reason")


def require_economic_value(context: EconomicContext) -> float:
    """Fail closed when the required economic quantity is unavailable."""
    if context.gross_value is None or context.expected_execution_cost is None:
        raise DecisionUtilityError("required economic value is unavailable")
    return context.gross_value - context.expected_execution_cost
