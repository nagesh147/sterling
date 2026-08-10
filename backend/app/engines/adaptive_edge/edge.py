"""Adaptive Edge prediction/opportunity contract.

The strategy-specific equation is intentionally not guessed here. A concrete
implementation must register an explicit formula ID from FORMULAS.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .feature_engine import FeatureSnapshot


@dataclass(frozen=True)
class EdgeAssessment:
    opportunity_id: str
    score: float
    confidence: float | None
    expected_gross_value: float | None
    formula_id: str
    formula_version: str
    inputs: Mapping[str, float]


class EdgeFormula(Protocol):
    formula_id: str
    formula_version: str

    def evaluate(self, snapshot: FeatureSnapshot) -> EdgeAssessment: ...


class StrategyFormulaLockedError(RuntimeError):
    """Raised instead of silently substituting an unrelated strategy formula."""


def evaluate_edge(snapshot: FeatureSnapshot, formula: EdgeFormula) -> EdgeAssessment:
    if not formula.formula_id.startswith("F-10"):
        raise StrategyFormulaLockedError(
            f"Adaptive Edge requires a strategy-specific formula ID; got {formula.formula_id}"
        )
    return formula.evaluate(snapshot)
