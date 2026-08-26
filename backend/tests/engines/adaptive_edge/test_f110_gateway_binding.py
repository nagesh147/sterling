from __future__ import annotations

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper
from app.engines.adaptive_edge.execution_adapter import ExecutionAdapter
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.f110_order_admission import expected_f110_admission_token
from app.engines.adaptive_edge.order_intent_factory import OrderIntentFactory, OrderIntentInputs


class Transport:
    def __init__(self):
        self.calls = 0

    def submit(self, intent):
        self.calls += 1
        return f"broker-{self.calls}"


def make_intent():
    return OrderIntentFactory.create(OrderIntentInputs(
        "sel-1", "NIFTY-CE", "BUY", 25, "v1", "2026-08-19T03:45:00Z"
    ))


def make_gateway(transport):
    return ExecutionGateway(
        ExecutionAdapter(transport),
        BrokerEventMapper({}),
        ExecutionEventRegistry(),
        authorized_formula_ids=("F-004",),
    )


def test_simulation_gateway_requires_f110_proof():
    transport = Transport()
    gateway = make_gateway(transport)
    intent = make_intent()
    with pytest.raises(PermissionError):
        gateway.submit(intent)
    assert transport.calls == 0


def test_simulation_gateway_accepts_only_intent_bound_f110_proof():
    transport = Transport()
    gateway = make_gateway(transport)
    intent = make_intent()
    assert gateway.submit(intent, f110_admission_token=expected_f110_admission_token(intent)) == "broker-1"
    assert transport.calls == 1


def test_f110_proof_cannot_be_reused_for_modified_intent():
    transport = Transport()
    gateway = make_gateway(transport)
    original = make_intent()
    modified = OrderIntentFactory.create(OrderIntentInputs(
        "sel-1", "NIFTY-CE", "BUY", 50, "v1", "2026-08-19T03:45:00Z"
    ))
    token = expected_f110_admission_token(original)
    with pytest.raises(PermissionError):
        gateway.submit(modified, f110_admission_token=token)
    assert transport.calls == 0
