import pytest

from app.engines.adaptive_edge.readiness import (
    REQUIRED_STRATEGY_FORMULAS,
    assess_strategy_readiness,
    require_strategy_ready,
)


def test_all_strategy_formulas_are_required():
    assert REQUIRED_STRATEGY_FORMULAS == tuple(
        f"F-{number:03d}" for number in range(101, 115)
    )


def test_current_strategy_is_not_executable():
    readiness = assess_strategy_readiness()
    assert readiness.executable is False
    assert readiness.unresolved_formula_ids == REQUIRED_STRATEGY_FORMULAS
    assert readiness.reason == "required_strategy_formulas_unresolved"


def test_require_strategy_ready_fails_closed():
    with pytest.raises(RuntimeError, match="required_strategy_formulas_unresolved|F-101"):
        require_strategy_ready()
