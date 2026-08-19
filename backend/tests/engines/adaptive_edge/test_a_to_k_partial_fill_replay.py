from __future__ import annotations

import hashlib
import json

from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus
from app.engines.adaptive_edge.position_projector import DeterministicPositionProjector
from app.engines.adaptive_edge.f112_f111_integration import *
from app.engines.adaptive_edge.f112_protection_envelope import F112ProtectionEnvelope
from app.engines.adaptive_edge.f111_lifecycle_state import F111LifecycleStateMachine, LifecycleInput
from app.engines.adaptive_edge.f113_reentry_admission import ReentryContext, evaluate_reentry
from app.engines.adaptive_edge.protection import ProtectionPolicy


def _event(event_id: str, intent: str, status, qty: int, price: float) -> CanonicalExecutionEvent:
    return CanonicalExecutionEvent(
        execution_event_id=event_id, order_intent_id=intent, event_type=status,
        event_time=f"2026-08-19T03:45:{event_id[-1]}0Z", filled_quantity=qty,
        fill_price=price, evidence_class="broker_fill",
    )


def _replay() -> str:
    projector = DeterministicPositionProjector(
        "position-1", "NIFTY-CE", side="BUY",
        order_side_map={"entry": "BUY", "exit": "SELL"},
    )
    protection = F112ProtectionEnvelope(
        ProtectionPolicy("replay", protective_stop_points=5, trail_points=2,
                         profit_lock_activation_points=4, profit_lock_offset_points=1),
        side="BUY", entry_price=100,
    )
    lifecycle = F111LifecycleStateMachine()
    trace = []

    for execution, mark, continuation in (
        (_event("e1", "entry", CanonicalExecutionStatus.PARTIALLY_FILLED, 10, 100), 100, 10.0),
        (_event("e2", "entry", CanonicalExecutionStatus.FILLED, 15, 110), 108, 10.0),
        (_event("e3", "exit", CanonicalExecutionStatus.PARTIALLY_FILLED, 10, 110), 106, 5.0),
        (_event("e4", "exit", CanonicalExecutionStatus.FILLED, 15, 105), 105, 0.0),
    ):
        position = projector.project(execution)
        protection_decision, protection_state = protection.update(mark)
        lifecycle_decision = lifecycle.evaluate(LifecycleInput(
            position_quantity=position.quantity,
            continuation_value=continuation,
            protection_hit=protection_decision.hit,
            emergency_reversal=False,
            session_cutoff=False,
        ))
        trace.append({
            "execution": execution.execution_event_id,
            "quantity": position.quantity,
            "average": position.average_price,
            "realized_pnl": projector.realized_pnl,
            "stop": protection_state.effective_stop,
            "lifecycle": lifecycle_decision.next_state.value,
            "action": lifecycle_decision.action.value,
        })

    trace.append(evaluate_reentry(ReentryContext(
        position_flat=projector.is_flat,
        prior_outcome_finalized=True,
        fresh_signal_valid=True,
        fresh_risk_authorized=True,
    )).admitted)
    return hashlib.sha256(json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_a_to_k_partial_fill_replay_is_deterministic():
    assert _replay() == _replay()
