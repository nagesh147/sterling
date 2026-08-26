"""The invented F-101..F-114 must stay unreachable.

model.py once held reconstructed F-101..F-114 equations that were never part of
the Master Mathematical Specification. They were replaced by shims that raise.
This file asserted the registry marked those ids DEPRECATED; the registry
settled on LOCKED instead, which carries the same consequence — not executable —
and is what the 2026-08-18 reconciliation records. What matters is that neither
route reaches an execution path, so both are asserted here.
"""
import pytest

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula, require_implemented
from app.engines.adaptive_edge.model import MarketFeatures, ProvisionalAdaptiveEdgeModelError, f101_feature_score


def test_provisional_formula_ids_are_not_executable_in_the_registry():
    for formula_id in (f"F-{number}" for number in range(101, 115)):
        assert get_formula(formula_id).status is FormulaStatus.LOCKED


def test_locked_formula_cannot_enter_execution_path():
    with pytest.raises(RuntimeError, match="not executable"):
        require_implemented("F-101")


def test_the_deprecated_implementation_itself_still_refuses_to_run():
    """The shim is the other half: calling the old code raises rather than returning a number."""
    features = MarketFeatures(
        trend=1.0, momentum=1.0, relative_volume=0.5,
        volatility_expansion=0.2, expected_move=2.0, confidence=0.9,
    )
    with pytest.raises(ProvisionalAdaptiveEdgeModelError, match="deprecated"):
        f101_feature_score(features)
