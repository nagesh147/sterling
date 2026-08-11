"""Feature -> Edge -> Economic Evaluation orchestration.

This module intentionally stops before risk authorization and execution. Those
steps require their own locked strategy contracts and platform integration.
"""
from __future__ import annotations

from dataclasses import dataclass

from .edge import EdgeAssessment, EdgeFormula, evaluate_edge
from .economic import EconomicAssessment, evaluate_economics
from .feature_engine import FeatureSnapshot


@dataclass(frozen=True)
class EvaluationResult:
    edge: EdgeAssessment
    economics: EconomicAssessment


def evaluate_candidate(
    snapshot: FeatureSnapshot,
    formula: EdgeFormula,
    *,
    execution_cost: float,
    minimum_net_value: float = 0.0,
) -> EvaluationResult:
    """Evaluate one causally valid candidate through the first three layers."""
    edge = evaluate_edge(snapshot, formula)
    economics = evaluate_economics(
        edge,
        execution_cost=execution_cost,
        minimum_net_value=minimum_net_value,
    )
    return EvaluationResult(edge=edge, economics=economics)
