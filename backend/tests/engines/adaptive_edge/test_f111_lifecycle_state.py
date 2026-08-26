from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f111_lifecycle_state import (
    F111LifecycleStateMachine,
    LifecycleAction,
    LifecycleInput,
    LifecycleState,
)


def test_f111_protection_then_hold_then_exit():
    machine = F111LifecycleStateMachine()
    decision = machine.evaluate(LifecycleInput(25, 10.0, False, False, False))
    assert decision.next_state is LifecycleState.PROTECTED
    assert decision.action is LifecycleAction.PROTECT

    decision = machine.evaluate(LifecycleInput(25, 5.0, False, False, False))
    assert decision.action is LifecycleAction.HOLD
    assert decision.next_state is LifecycleState.PROTECTED

    decision = machine.evaluate(LifecycleInput(25, 5.0, True, False, False))
    assert decision.action is LifecycleAction.EXIT
    assert decision.next_state is LifecycleState.EXIT_PENDING


def test_f111_fails_closed_on_missing_continuation_value():
    machine = F111LifecycleStateMachine()
    with pytest.raises(ValueError, match="missing continuation_value"):
        machine.evaluate(LifecycleInput(25, None, False, False, False))


def test_f111_emergency_reversal_and_cutoff_exit():
    for emergency, cutoff in ((True, False), (False, True)):
        machine = F111LifecycleStateMachine()
        decision = machine.evaluate(LifecycleInput(25, 10.0, False, emergency, cutoff))
        assert decision.action is LifecycleAction.EXIT
        assert decision.next_state is LifecycleState.EXIT_PENDING


def test_f111_closed_position_is_terminal():
    machine = F111LifecycleStateMachine()
    decision = machine.evaluate(LifecycleInput(0, 10.0, False, False, False))
    assert decision.next_state is LifecycleState.CLOSED
    with pytest.raises(ValueError, match="closed lifecycle"):
        machine.evaluate(LifecycleInput(25, 10.0, False, False, False))
