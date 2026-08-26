from __future__ import annotations

import hashlib
import json

from app.engines.adaptive_edge.f111_lifecycle_state import F111LifecycleStateMachine, LifecycleInput
from app.engines.adaptive_edge.f112_protection_envelope import F112ProtectionEnvelope
from app.engines.adaptive_edge.f113_reentry_admission import ReentryContext, evaluate_reentry
from app.engines.adaptive_edge.protection import ProtectionPolicy


def replay() -> str:
    protection = F112ProtectionEnvelope(
        ProtectionPolicy("replay", protective_stop_points=5, trail_points=2,
                         profit_lock_activation_points=4, profit_lock_offset_points=1),
        side="BUY", entry_price=100,
    )
    lifecycle = F111LifecycleStateMachine()
    trace = []
    for mark, continuation in ((100, 10.0), (104, 10.0), (108, 10.0), (105, 10.0), (100, 0.0)):
        protection_decision, protection_state = protection.update(mark)
        lifecycle_decision = lifecycle.evaluate(LifecycleInput(
            position_quantity=25,
            continuation_value=continuation,
            protection_hit=protection_decision.hit,
            emergency_reversal=False,
            session_cutoff=False,
        ))
        trace.append({
            "mark": mark,
            "stop": protection_state.effective_stop,
            "extreme": protection_state.favorable_extreme,
            "lock": protection_state.lock_active,
            "lifecycle": lifecycle_decision.next_state.value,
            "action": lifecycle_decision.action.value,
        })
        if lifecycle_decision.action.value == "EXIT":
            break
    trace.append(evaluate_reentry(ReentryContext(False, False, True, True)).admitted)
    payload = json.dumps(trace, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_full_governed_lifecycle_replay_is_deterministic():
    assert replay() == replay()
