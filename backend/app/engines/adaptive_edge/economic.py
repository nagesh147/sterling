"""Economic evaluation anchored to Master Specification §§31 and 66.

This module calculates the source-defined economic relationship only.
Eligibility is a downstream conservative-EV decision and is deliberately not
inferred from raw NetEV here.
"""
from __future__ import annotations

from dataclasses import dataclass

from .edge import EdgeAssessment


@dataclass(frozen=True)
class EconomicAssessment:
    expected_gross_value: float
    expected_execution_cost: float
    expected_net_value: float
    formula_id: str = "MS-31/66"
    formula_version: str = "1.0"


def evaluate_economics(
    edge: EdgeAssessment,
    *,
    execution_cost: float,
) -> EconomicAssessment:
    """Compute NetEV = E[Profit] - E[Loss] - E[ExecutionCost].

    This function intentionally does not implement the downstream eligibility
    rule. §66 requires a positive conservative estimate; that estimate and
    its lower-confidence construction are separate inputs and remain blocked
    until their source-defined calibration method is recovered.
    """
    if edge.expected_gross_value is None:
        raise ValueError("expected gross value is required")

    net = edge.expected_gross_value - execution_cost
    return EconomicAssessment(
        expected_gross_value=edge.expected_gross_value,
        expected_execution_cost=execution_cost,
        expected_net_value=net,
    )
