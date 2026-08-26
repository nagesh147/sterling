from __future__ import annotations

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus, ExecutionAdapter
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.execution_path import GovernedExecutionPath
from app.engines.adaptive_edge.position_projector import DeterministicPositionProjector


class Transport:
    def __init__(self):
        self.calls = 0

    def submit(self, intent):
        self.calls += 1
        return f"broker-{self.calls}"


def test_governed_path_supplies_f110_proof_before_gateway_submission():
    transport = Transport()
    gateway = ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
        authorized_formula_ids=("F-004",),
    )
    projector = DeterministicPositionProjector("position-1", "NIFTY-CE", side="BUY")
    path = GovernedExecutionPath(gateway, projector)

    def broker_event(intent, reference):
        return BrokerExecutionEvent(
            broker_event_id="evt-1", order_intent_id=intent.order_intent_id,
            broker_status="FILLED", event_time="2026-08-19T03:45:02Z",
            filled_quantity=25, fill_price=100.0,
        )

    result = path.submit_and_project(
        selection_id="sel-1", instrument_id="NIFTY-CE", side="BUY", quantity=25,
        intent_version="v1", created_at="2026-08-19T03:45:00Z",
        broker_event_factory=broker_event,
    )
    assert result.intent.quantity == 25
    assert result.execution_event.event_type is CanonicalExecutionStatus.FILLED
    assert transport.calls == 1


def test_gateway_rejects_direct_simulation_submission_without_f110_proof():
    transport = Transport()
    gateway = ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(), authorized_formula_ids=("F-004",),
    )
    from app.engines.adaptive_edge.order_intent_factory import OrderIntentFactory, OrderIntentInputs
    intent = OrderIntentFactory.create(OrderIntentInputs("sel", "NIFTY-CE", "BUY", 25, "v1", "2026-08-19T03:45:00Z"))
    with pytest.raises(PermissionError):
        gateway.submit(intent)
    assert transport.calls == 0
