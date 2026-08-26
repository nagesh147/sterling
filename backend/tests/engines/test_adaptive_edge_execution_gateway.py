from dataclasses import dataclass
import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus, CanonicalOrderIntent, ExecutionAdapter
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gate import ExecutionBlockedError
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway


@dataclass
class FakeTransport:
    calls: int = 0

    def submit(self, intent: CanonicalOrderIntent) -> str:
        self.calls += 1
        return "broker-order-1"


def make_intent() -> CanonicalOrderIntent:
    return CanonicalOrderIntent(
        order_intent_id="oi-1", selection_id="sel-1", instrument_id="NIFTY-CE",
        side="BUY", quantity=50, intent_version="v1", idempotency_key="idem-1",
        created_at="2026-08-14T03:45:00+00:00",
    )


def test_gateway_blocks_submission_when_strategy_formulas_are_locked():
    transport = FakeTransport()
    registry = ExecutionEventRegistry()
    gateway = ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        registry,
    )

    with pytest.raises(ExecutionBlockedError):
        gateway.submit(make_intent())
    assert transport.calls == 0


def test_gateway_composes_submission_and_broker_event_paths():
    transport = FakeTransport()
    registry = ExecutionEventRegistry()
    gateway = ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        registry,
    )

    assert gateway.submit(make_intent(), formula_ids=("F-004",)) == "broker-order-1"
    event = gateway.receive(BrokerExecutionEvent(
        broker_event_id="ex-1", order_intent_id="oi-1", broker_status="COMPLETE",
        event_time="2026-08-14T03:45:02+00:00", filled_quantity=50, fill_price=120.5,
    ))

    assert event.event_type is CanonicalExecutionStatus.FILLED
    assert registry.record(event) is False
    assert transport.calls == 1
