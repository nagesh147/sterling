"""Economic evaluation for Adaptive Edge.

Prediction and risk are deliberately not part of this module. This module
answers only whether the expected opportunity remains economically viable
after execution costs.
"""
from __future__ import annotations

from dataclasses import dataclass

from .edge import EdgeAssessment
from .formula_registry import require_implemented


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
    definition = require_implemented("F-004")
    if execution_cost < 0:
        # A negative cost is a cost that pays you. It inflates net value and so
        # turns unviable opportunities eligible — fail closed instead.
        raise ValueError(f"execution cost cannot be negative: {execution_cost}")
    gross = edge.expected_gross_value
    if gross is None:
        return EconomicAssessment(
            expected_gross_value=0.0,
            expected_execution_cost=execution_cost,
            expected_net_value=0.0,
            eligible=False,
            formula_id=definition.formula_id,
            formula_version=definition.version,
            reason="missing_expected_gross_value",
        )

    net = gross - execution_cost
    # Strictly greater: the source rule is "EV_conservative <= 0 -> NO_TRADE",
    # so an opportunity whose expected net value is exactly the threshold is not
    # eligible. With the default threshold of zero, `>=` admitted trades with no
    # expected profit and real risk.
    eligible = net > minimum_net_value
    return EconomicAssessment(
        expected_gross_value=gross,
        expected_execution_cost=execution_cost,
        expected_net_value=net,
        eligible=eligible,
        formula_id=definition.formula_id,
        formula_version=definition.version,
        reason=None if eligible else "expected_net_value_below_threshold",
    )
