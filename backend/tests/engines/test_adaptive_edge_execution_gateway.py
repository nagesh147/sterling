from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.execution_adapter import (
    CanonicalExecutionStatus,
    CanonicalOrderIntent,
    ExecutionAdapter,
)
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway


def make_intent() -> CanonicalOrderIntent:
    return CanonicalOrderIntent(
        order_intent_id="oi-1",
        selection_id="sel-1",
        instrument_id="NIFTY-OPT-1",
        side="BUY",
        quantity=50,
        intent_version="1",
        idempotency_key="idem-1",
        created_at="2026-08-14T00:00:00+00:00",
    )


def test_gateway_separates_submission_from_execution():
    adapter = ExecutionAdapter()
    gateway = ExecutionGateway(
        adapter,
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )

    broker_order_id = gateway.submit(make_intent())
    assert broker_order_id

    event = gateway.receive(
        BrokerExecutionEvent(
            broker_event_id="be-1",
            order_intent_id="oi-1",
            broker_status="COMPLETE",
            event_time="2026-08-14T00:00:01+00:00",
            broker_reference=broker_order_id,
            filled_quantity=50,
            fill_price=120.5,
        )
    )

    assert event.event_type is CanonicalExecutionStatus.FILLED
    assert event.order_intent_id == "oi-1"
    assert event.filled_quantity == 50


def test_gateway_maps_unknown_status_fail_closed():
    adapter = ExecutionAdapter()
    gateway = ExecutionGateway(
        adapter,
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )

    event = gateway.receive(
        BrokerExecutionEvent(
            broker_event_id="be-unknown",
            order_intent_id="oi-1",
            broker_status="NEW_PROVIDER_STATUS",
            event_time="2026-08-14T00:00:01+00:00",
        )
    )

    assert event.event_type is CanonicalExecutionStatus.UNKNOWN


def test_gateway_event_replay_is_idempotent():
    adapter = ExecutionAdapter()
    gateway = ExecutionGateway(
        adapter,
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )
    broker_event = BrokerExecutionEvent(
        broker_event_id="be-repeat",
        order_intent_id="oi-1",
        broker_status="COMPLETE",
        event_time="2026-08-14T00:00:01+00:00",
        filled_quantity=50,
        fill_price=120.5,
    )

    first = gateway.receive(broker_event)
    second = gateway.receive(broker_event)
    assert first == second
