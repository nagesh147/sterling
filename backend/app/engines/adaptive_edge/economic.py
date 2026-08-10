"""Economic evaluation for Adaptive Edge.

Prediction and risk are deliberately not part of this module. This module
answers only whether the expected opportunity remains economically viable
after execution costs.
"""
from __future__ import annotations

from dataclasses import dataclass

from .edge import EdgeAssessment


@dataclass(frozen=True)
class EconomicAssessment:
    expected_gross_value: float
    expected_execution_cost: float
    expected_net_value: float
    eligible: bool
    formula_id: str = "F-004"
    formula_version: str = "1.0"
    reason: str | None = None


def evaluate_economics(
    edge: EdgeAssessment,
    *,
    execution_cost: float,
    minimum_net_value: float = 0.0,
) -> EconomicAssessment:
    gross = edge.expected_gross_value
    if gross is None:
        return EconomicAssessment(
            expected_gross_value=0.0,
            expected_execution_cost=execution_cost,
            expected_net_value=0.0,
            eligible=False,
            reason="missing_expected_gross_value",
        )

    net = gross - execution_cost
    eligible = net >= minimum_net_value
    return EconomicAssessment(
        expected_gross_value=gross,
        expected_execution_cost=execution_cost,
        expected_net_value=net,
        eligible=eligible,
        reason=None if eligible else "expected_net_value_below_threshold",
    )
