import pytest

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula, require_implemented


def test_strategy_specific_formulas_are_implemented():
    for formula_id in ("F-101", "F-102", "F-103", "F-104", "F-105", "F-106", "F-107", "F-108", "F-109", "F-110", "F-111", "F-112", "F-113", "F-114"):
        assert get_formula(formula_id).status is FormulaStatus.IMPLEMENTED
        assert get_formula(formula_id).version == "1.0"


def test_economic_formula_is_implemented():
    formula = require_implemented("F-004")
    assert formula.version == "1.0"


def test_anchored_formula_cannot_be_required_as_implemented():
    with pytest.raises(RuntimeError, match="not executable"):
        require_implemented("F-001")
