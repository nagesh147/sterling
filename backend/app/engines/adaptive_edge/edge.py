"""Adaptive Edge prediction/opportunity contract.

The strategy-specific equation is intentionally not guessed here. A concrete
implementation must register an explicit formula ID from the canonical
Adaptive Edge formula registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .feature_engine import FeatureSnapshot
from .formula_registry import FormulaStatus, get_formula


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
    definition = get_formula(formula.formula_id)
    if not formula.formula_id.startswith("F-10") or definition.status is not FormulaStatus.IMPLEMENTED:
        raise StrategyFormulaLockedError(
            f"Adaptive Edge formula {formula.formula_id} is not executable; exact strategy mathematics must be recovered first"
        )
    if formula.formula_version != definition.version:
        raise StrategyFormulaLockedError(
            f"formula version mismatch for {formula.formula_id}: implementation={formula.formula_version}, registry={definition.version}"
        )
    return formula.evaluate(snapshot)
