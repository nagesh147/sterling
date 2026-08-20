from __future__ import annotations

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus, ExecutionAdapter
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.order_intent_factory import OrderIntentFactory, OrderIntentInputs


class Transport:
    def __init__(self):
        self.calls = 0

    def submit(self, intent):
        self.calls += 1
        return f"ref-{self.calls}"


def test_duplicate_intent_submission_is_not_implicitly_authorized():
    transport = Transport()
    gateway = ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )
    intent = OrderIntentFactory.create(
        OrderIntentInputs("sel", "NIFTY-CE", "BUY", 25, "v1", "2026-08-19T03:45:00+00:00")
    )
    with pytest.raises(Exception):
        gateway.submit(intent)
    assert transport.calls == 0


def test_unmapped_broker_status_fails_closed_before_position_projection():
    """An unmapped status must never reach position projection.

    The gate is `validate()`, not `map()`: mapping an unrecognised provider
    status to UNKNOWN keeps the fill data the reconciler needs, and every
    production consumer -- `ExecutionGateway.receive` included -- validates
    before using the event. So the refusal is asserted where it actually
    happens rather than at translation time.
    """
    mapper = BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED})
    event = BrokerExecutionEvent(
        broker_event_id="evt-1",
        order_intent_id="intent-1",
        broker_status="UNKNOWN",
        event_time="2026-08-19T03:45:02+00:00",
        filled_quantity=25,
        fill_price=100.0,
    )
    canonical = mapper.map(event)
    assert canonical.event_type is CanonicalExecutionStatus.UNKNOWN
    with pytest.raises(Exception):
        canonical.validate()


def test_invalid_fill_quantity_fails_closed():
    mapper = BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED})
    event = BrokerExecutionEvent(
        broker_event_id="evt-1",
        order_intent_id="intent-1",
        broker_status="FILLED",
        event_time="2026-08-19T03:45:02+00:00",
        filled_quantity=-25,
        fill_price=100.0,
    )
    with pytest.raises(Exception):
        mapper.map(event)
