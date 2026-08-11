"""Canonical economic evaluation for Adaptive Edge.

Implements the relationships explicitly defined by the Master Mathematical
Specification. No learned threshold is invented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .canonical_math import ExecutionCost, expected_net_value, expected_value_per_risk, target_stop_ev


@dataclass(frozen=True)
class EconomicEvaluation:
    expected_gross_value: float
    execution_cost: ExecutionCost
    expected_net_value: float
    conservative_net_value: float
    effective_risk: float
    ev_per_risk: float

    @property
    def eligible(self) -> bool:
        return self.conservative_net_value > 0.0


def evaluate(
    *,
    expected_gross_value: float,
    execution_cost: ExecutionCost,
    conservative_net_value: float,
    effective_risk: float,
) -> EconomicEvaluation:
    net = expected_net_value(expected_gross_value, execution_cost)
    return EconomicEvaluation(
        expected_gross_value=expected_gross_value,
        execution_cost=execution_cost,
        expected_net_value=net,
        conservative_net_value=conservative_net_value,
        effective_risk=effective_risk,
        ev_per_risk=expected_value_per_risk(conservative_net_value, effective_risk) if effective_risk > 0 else 0.0,
    )


def candidate_target_stop_value(
    *,
    target_probability: float,
    expected_gain: float,
    stop_probability: float,
    expected_loss: float,
    execution_cost: ExecutionCost,
) -> float:
    return target_stop_ev(
        target_probability,
        expected_gain,
        stop_probability,
        expected_loss,
        execution_cost.total,
    )
