import pytest

from app.engines.adaptive_edge.execution_gate import (
    REQUIRED_STRATEGY_FORMULAS,
    ExecutionBlockedError,
    ExecutionGateStatus,
    evaluate_execution_gate,
    require_execution_authorized,
)


def test_all_strategy_specific_formulas_are_required():
    assert REQUIRED_STRATEGY_FORMULAS == tuple(
        f"F-{number:03d}" for number in range(101, 115)
    )


def test_current_adaptive_edge_is_authorized():
    decision = evaluate_execution_gate()

    assert decision.status is ExecutionGateStatus.AUTHORIZED
    assert decision.authorized is True
    assert decision.blocking_formulas == ()
    assert decision.reason is None


def test_unknown_formula_is_fail_closed():
    decision = evaluate_execution_gate(("F-999",))

    assert decision.status is ExecutionGateStatus.BLOCKED
    assert decision.blocking_formulas == ("F-999",)


def test_gate_raises_when_execution_is_not_authorized():
    with pytest.raises(ExecutionBlockedError) as exc_info:
        require_execution_authorized(("F-999",))

    assert exc_info.value.decision.blocking_formulas == ("F-999",)


def test_gate_can_authorize_a_fully_implemented_registry_subset():
    decision = evaluate_execution_gate(("F-004",))

    assert decision.status is ExecutionGateStatus.AUTHORIZED
    assert decision.authorized is True
    assert decision.blocking_formulas == ()
