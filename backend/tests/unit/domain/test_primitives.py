from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.primitives import (
    EventEnvelope,
    EventID,
    InstrumentID,
    Money,
    Probability,
    Price,
    Quantity,
    Timestamp,
    Version,
)


UTC = timezone.utc


def test_typed_identifiers_are_not_interchangeable() -> None:
    assert InstrumentID(value="ABC") != EventID(value="ABC")


def test_identifiers_are_immutable() -> None:
    identifier = InstrumentID(value="ABC")
    with pytest.raises(ValidationError):
        identifier.value = "DEF"


def test_timestamp_requires_timezone_and_normalizes_to_utc() -> None:
    timestamp = Timestamp(value=datetime(2026, 8, 11, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))))
    assert timestamp.value == datetime(2026, 8, 11, 4, 30, tzinfo=UTC)

    with pytest.raises(ValidationError):
        Timestamp(value=datetime(2026, 8, 11, 10, 0))


def test_probability_is_closed_interval() -> None:
    assert Probability(value="0").value == Decimal("0")
    assert Probability(value="1").value == Decimal("1")

    with pytest.raises(ValidationError):
        Probability(value="-0.01")
    with pytest.raises(ValidationError):
        Probability(value="1.01")


def test_financial_values_reject_non_finite_values() -> None:
    for primitive in (Price, Quantity):
        with pytest.raises(ValidationError):
            primitive(value="NaN")
        with pytest.raises(ValidationError):
            primitive(value="Infinity")

    with pytest.raises(ValidationError):
        Money(amount="Infinity", currency="INR")


def test_money_requires_currency() -> None:
    assert Money(amount="100.25", currency="INR").currency.value == "INR"


def test_event_envelope_rejects_receipt_before_event() -> None:
    event_time = Timestamp(value=datetime(2026, 8, 11, 4, 30, tzinfo=UTC))
    received_time = Timestamp(value=datetime(2026, 8, 11, 4, 29, tzinfo=UTC))

    with pytest.raises(ValidationError):
        EventEnvelope(
            event_id=EventID(value="evt-1"),
            event_type="QUOTE",
            event_time=event_time,
            received_time=received_time,
            source="test",
            schema_version=Version(value="1.0.0"),
            sequence=0,
            payload={},
        )


def test_event_causal_availability_uses_receipt_time() -> None:
    event_time = Timestamp(value=datetime(2026, 8, 11, 4, 30, tzinfo=UTC))
    received_time = Timestamp(value=datetime(2026, 8, 11, 4, 30, 500000, tzinfo=UTC))
    event = EventEnvelope(
        event_id=EventID(value="evt-1"),
        event_type="QUOTE",
        event_time=event_time,
        received_time=received_time,
        source="test",
        schema_version=Version(value="1.0.0"),
        sequence=0,
        payload={},
    )

    assert not event.is_causally_available_at(event_time)
    assert event.is_causally_available_at(received_time)
