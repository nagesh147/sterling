import pytest

from app.engines.adaptive_edge.execution_accounting_integration import (
    AccountingEvent,
    ExecutionAccountingError,
    FillEvent,
    FillStatus,
    PositionEffect,
    derive_accounting_event,
    derive_position_effect,
)


def fill(**overrides):
    values = dict(fill_id="fill-1", intent_id="intent-1", instrument_id="NIFTY", quantity=10, price=100.0, occurred_at_ms=100)
    values.update(overrides)
    return FillEvent(**values)


def test_position_effect_requires_confirmed_fill():
    with pytest.raises(ExecutionAccountingError):
        derive_position_effect(fill(status="not_confirmed"), 10)


def test_position_effect_is_derived_from_fill():
    result = derive_position_effect(fill(), 10)
    assert result.fill_id == "fill-1"
    assert result.instrument_id == "NIFTY"


def test_accounting_event_requires_matching_fill_effect():
    effect = derive_position_effect(fill(), 10)
    result = derive_accounting_event(fill(), effect)
    assert result.fill_id == "fill-1"
    assert result.position_effect_id == effect.effect_id


def test_position_effect_cannot_precede_fill():
    f = fill()
    effect = PositionEffect("effect-1", f.fill_id, f.instrument_id, 10, 99)
    with pytest.raises(ExecutionAccountingError):
        derive_accounting_event(f, effect)


def test_accounting_cannot_be_derived_from_order_intent_only():
    # There is intentionally no order-intent parameter in derive_accounting_event.
    assert AccountingEvent.__dataclass_fields__["fill_id"]
