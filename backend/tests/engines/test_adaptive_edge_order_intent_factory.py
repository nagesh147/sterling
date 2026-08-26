from __future__ import annotations

import pytest

from app.engines.adaptive_edge.execution_adapter import CanonicalOrderIntent
from app.engines.adaptive_edge.order_intent_factory import OrderIntentFactory, OrderIntentInputs


def inputs(**overrides):
    values = dict(
        selection_id="sel-001",
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
        quantity=25,
        intent_version="1",
        created_at="2026-08-19T09:30:00Z",
    )
    values.update(overrides)
    return OrderIntentInputs(**values)


def test_factory_creates_valid_canonical_intent() -> None:
    intent = OrderIntentFactory.create(inputs())
    assert isinstance(intent, CanonicalOrderIntent)
    intent.validate()
    assert intent.quantity == 25
    assert intent.side == "BUY"


def test_factory_is_deterministic_for_identical_inputs() -> None:
    a = OrderIntentFactory.create(inputs())
    b = OrderIntentFactory.create(inputs())
    assert a == b
    assert a.fingerprint() == b.fingerprint()


def test_factory_changes_identity_when_causal_input_changes() -> None:
    a = OrderIntentFactory.create(inputs(quantity=25))
    b = OrderIntentFactory.create(inputs(quantity=50))
    assert a.order_intent_id != b.order_intent_id
    assert a.idempotency_key != b.idempotency_key

@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"selection_id": ""}, "selection_id"),
        ({"instrument_id": ""}, "instrument_id"),
        ({"side": "HOLD"}, "side"),
        ({"quantity": 0}, "quantity"),
        ({"intent_version": ""}, "intent_version"),
        ({"created_at": ""}, "created_at"),
    ],
)
def test_factory_fails_closed(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        OrderIntentFactory.create(inputs(**overrides))
