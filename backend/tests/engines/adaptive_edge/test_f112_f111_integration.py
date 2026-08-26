from __future__ import annotations

from app.engines.adaptive_edge.f111_lifecycle_state import F111LifecycleStateMachine, LifecycleAction, LifecycleInput, LifecycleState
from app.engines.adaptive_edge.f112_protection_envelope import F112ProtectionEnvelope
from app.engines.adaptive_edge.protection import ProtectionPolicy


def test_f112_authority_drives_f111_exit_and_flatten_boundary():
    envelope = F112ProtectionEnvelope(
        ProtectionPolicy("test", protective_stop_points=5, trail_points=2,
                         profit_lock_activation_points=4, profit_lock_offset_points=1),
        side="BUY", entry_price=100,
    )
    machine = F111LifecycleStateMachine()
    _, state = envelope.update(108)
    assert state.effective_stop is not None
    decision, state = envelope.update(105)
    lifecycle = machine.evaluate(LifecycleInput(
        position_quantity=25,
        continuation_value=10.0,
        protection_hit=decision.hit,
        emergency_reversal=False,
        session_cutoff=False,
    ))
    assert lifecycle.action is LifecycleAction.EXIT
    assert lifecycle.next_state is LifecycleState.EXIT_PENDING

    closed = machine.evaluate(LifecycleInput(0, 0.0, False, False, False))
    assert closed.next_state is LifecycleState.CLOSED


def test_f112_f111_never_reopens_closed_position():
    machine = F111LifecycleStateMachine()
    machine.evaluate(LifecycleInput(0, 0.0, False, False, False))
    try:
        machine.evaluate(LifecycleInput(25, 10.0, False, False, False))
    except ValueError:
        pass
    else:
        raise AssertionError("closed lifecycle must not reopen")
