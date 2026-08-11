"""Adaptive Edge prediction/opportunity boundary.

The opportunity boundary is intentionally source-driven. The deprecated
F-101..F-114 compatibility registry is not used to authorize strategy logic.
A concrete edge implementation may be supplied only when its source anchor
and learned parameters are available.
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
    source_anchor: str

    def evaluate(self, snapshot: FeatureSnapshot) -> EdgeAssessment: ...


class StrategyFormulaLockedError(RuntimeError):
    """Raised when an edge implementation lacks an executable source anchor."""


def evaluate_edge(snapshot: FeatureSnapshot, formula: EdgeFormula) -> EdgeAssessment:
    source_anchor = getattr(formula, "source_anchor", "")
    if not source_anchor:
        raise StrategyFormulaLockedError(
            "Adaptive Edge edge formula has no authoritative specification anchor"
        )
    if not formula.formula_id or not formula.formula_version:
        raise StrategyFormulaLockedError(
            "Adaptive Edge edge formula must declare an ID and version"
        )
    snapshot.assert_causal(snapshot.observation_time)
    return formula.evaluate(snapshot)
