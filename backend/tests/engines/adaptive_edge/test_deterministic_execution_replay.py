from __future__ import annotations

import hashlib
import json

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus, ExecutionAdapter
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.execution_path import GovernedExecutionPath
from app.engines.adaptive_edge.position_projector import DeterministicPositionProjector


class Transport:
    def submit(self, intent):
        return "broker-replay-1"


def replay_trace() -> str:
    gateway = ExecutionGateway(
        ExecutionAdapter(Transport()),
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
        authorized_formula_ids=("F-004",),
    )
    projector = DeterministicPositionProjector("position-1", "NIFTY26AUG24500CE", side="BUY")
    path = GovernedExecutionPath(gateway, projector)
    result = path.submit_and_project(
        selection_id="selection-1",
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
        quantity=25,
        intent_version="v1",
        created_at="2026-08-19T03:45:00+00:00",
        broker_event_factory=lambda intent, reference: BrokerExecutionEvent(
            broker_event_id="broker-event-1",
            order_intent_id=intent.order_intent_id,
            broker_status="COMPLETE",
            event_time="2026-08-19T03:45:02+00:00",
            filled_quantity=25,
            fill_price=120.5,
        ),
    )
    canonical = {
        "intent": result.intent.order_intent_id,
        "idempotency": result.intent.idempotency_key,
        "broker_reference": result.broker_reference,
        "execution_event": result.execution_event.execution_event_id,
        "position": {
            "quantity": result.position.quantity,
            "average_price": result.position.average_price,
            "lifecycle": result.position.lifecycle_state,
        },
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def test_duplicate_replay_produces_identical_trace_hash():
    assert replay_trace() == replay_trace()
