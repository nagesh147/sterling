import pytest

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula, require_implemented


def test_provisional_formula_ids_are_deprecated():
    for formula_id in (f"F-{number}" for number in range(101, 115)):
        assert get_formula(formula_id).status is FormulaStatus.DEPRECATED


def test_deprecated_formula_cannot_enter_execution_path():
    with pytest.raises(RuntimeError, match="deprecated"):
        require_implemented("F-101")
