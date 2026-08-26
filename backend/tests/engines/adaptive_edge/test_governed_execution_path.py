from __future__ import annotations

from dataclasses import dataclass

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus, ExecutionAdapter
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.execution_path import GovernedExecutionPath
from app.engines.adaptive_edge.position_projector import DeterministicPositionProjector
from app.engines.adaptive_edge.protection import ProtectionPolicy


@dataclass
class Transport:
    calls: int = 0

    def submit(self, intent):
        self.calls += 1
        return f"broker-{self.calls}"


def make_gateway(transport: Transport) -> ExecutionGateway:
    return ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
        authorized_formula_ids=("F-004",),
    )


def broker_event(intent, reference, event_id="evt-1", quantity=25, price=100.0):
    return BrokerExecutionEvent(
        broker_event_id=event_id,
        order_intent_id=intent.order_intent_id,
        broker_status="COMPLETE",
        event_time="2026-08-19T03:45:02+00:00",
        filled_quantity=quantity,
        fill_price=price,
    )


def test_full_governed_path_is_deterministic():
    def run():
        transport = Transport()
        gateway = make_gateway(transport)
        projector = DeterministicPositionProjector("pos-1", "NIFTY-CE", side="BUY")
        path = GovernedExecutionPath(
            gateway,
            projector,
            protection_policy=ProtectionPolicy(
                label="test", protective_stop_points=5, trail_points=2,
                profit_lock_activation_points=4, profit_lock_offset_points=1,
            ),
        )
        result = path.submit_and_project(
            selection_id="sel-1", instrument_id="NIFTY-CE", side="BUY", quantity=25,
            intent_version="v1", created_at="2026-08-19T03:45:00+00:00",
            broker_event_factory=broker_event, entry_price=100, mark=104,
        )
        return (
            result.intent.order_intent_id,
            result.intent.idempotency_key,
            result.broker_reference,
            result.execution_event.execution_event_id,
            result.position.quantity,
            result.position.average_price,
            result.protection.lock_active if result.protection else None,
        )

    assert run() == run()


def test_non_fill_does_not_change_position():
    transport = Transport()
    gateway = make_gateway(transport)
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE", side="BUY")
    path = GovernedExecutionPath(gateway, projector)

    # A non-fill broker status must be rejected by this intentionally minimal mapper,
    # preventing accidental position mutation from an unmapped broker event.
    try:
        path.submit_and_project(
            selection_id="sel-1", instrument_id="NIFTY-CE", side="BUY", quantity=25,
            intent_version="v1", created_at="2026-08-19T03:45:00+00:00",
            broker_event_factory=lambda intent, ref: BrokerExecutionEvent(
                broker_event_id="evt-cancel",
                order_intent_id=intent.order_intent_id,
                broker_status="CANCELLED",
                event_time="2026-08-19T03:45:02+00:00",
                filled_quantity=0,
                fill_price=None,
            ),
        )
    except Exception:
        pass
    assert projector.current_quantity == 0
