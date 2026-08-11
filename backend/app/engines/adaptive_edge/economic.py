"""Economic evaluation anchored to Master Specification §§31 and 66.

Prediction and risk are deliberately not part of this module. This module
answers only whether expected opportunity remains economically viable after
execution costs.
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
    formula_id: str = "MS-31/66"
    formula_version: str = "1.0"
    reason: str | None = None


def evaluate_economics(
    edge: EdgeAssessment,
    *,
    execution_cost: float,
) -> EconomicAssessment:
    if execution_cost < 0:
        raise ValueError("execution_cost cannot be negative")

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
    # Master Specification §§34-35 and §66 require positive conservative/net EV;
    # this layer only performs the non-conservative economic subtraction.
    eligible = net > 0.0
    return EconomicAssessment(
        expected_gross_value=gross,
        expected_execution_cost=execution_cost,
        expected_net_value=net,
        eligible=eligible,
        reason=None if eligible else "expected_net_value_not_positive",
    )
