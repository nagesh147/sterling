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


def test_friction_expectancy_gate_authorizes_viable_trade():
    from app.engines.adaptive_edge.execution_gate import evaluate_friction_expectancy_gate

    # 1 lot NIFTY (25 qty), Entry 100, Target 150 (gain = 50 * 25 = 1250 INR > 240)
    decision = evaluate_friction_expectancy_gate(
        entry_price=100.0,
        target_price=150.0,
        lot_size=25,
        estimated_friction_inr=60.0,
        min_friction_multiplier=4.0,
    )
    assert decision.authorized is True
    assert decision.expected_gain_inr == 1250.0
    assert decision.friction_ratio == 20.83
    assert decision.reason is None


def test_friction_expectancy_gate_blocks_low_expectancy_trade():
    from app.engines.adaptive_edge.execution_gate import evaluate_friction_expectancy_gate

    # 1 lot NIFTY (25 qty), Entry 100, Target 105 (gain = 5 * 25 = 125 INR < 240)
    decision = evaluate_friction_expectancy_gate(
        entry_price=100.0,
        target_price=105.0,
        lot_size=25,
        estimated_friction_inr=60.0,
        min_friction_multiplier=4.0,
    )
    assert decision.authorized is False
    assert decision.expected_gain_inr == 125.0
    assert decision.friction_ratio == 2.08
    assert "expected_gain_below_friction_threshold" in decision.reason
