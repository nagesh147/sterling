from __future__ import annotations

import pytest

from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus


def test_f111_fill_requires_quantity_and_price() -> None:
    event = CanonicalExecutionEvent(
        execution_event_id="evt-1",
        order_intent_id="ord-1",
        event_type=CanonicalExecutionStatus.FILLED,
        event_time="2026-08-17T09:20:00+05:30",
        filled_quantity=25,
        fill_price=120.5,
    )
    event.validate()


def test_f111_non_fill_cannot_carry_fill_data() -> None:
    event = CanonicalExecutionEvent(
        execution_event_id="evt-1",
        order_intent_id="ord-1",
        event_type=CanonicalExecutionStatus.ACKNOWLEDGED,
        event_time="2026-08-17T09:20:00+05:30",
        filled_quantity=25,
        fill_price=120.5,
    )
    with pytest.raises(ValueError, match="non-fill events"):
        event.validate()


def test_f111_partial_fill_is_distinct_from_full_fill() -> None:
    event = CanonicalExecutionEvent(
        execution_event_id="evt-1",
        order_intent_id="ord-1",
        event_type=CanonicalExecutionStatus.PARTIALLY_FILLED,
        event_time="2026-08-17T09:20:00+05:30",
        filled_quantity=10,
        fill_price=120.5,
    )
    event.validate()
    assert event.event_type is CanonicalExecutionStatus.PARTIALLY_FILLED


def test_f111_negative_fill_is_rejected() -> None:
    event = CanonicalExecutionEvent(
        execution_event_id="evt-1",
        order_intent_id="ord-1",
        event_type=CanonicalExecutionStatus.FILLED,
        event_time="2026-08-17T09:20:00+05:30",
        filled_quantity=-1,
        fill_price=120.5,
    )
    with pytest.raises(ValueError, match="negative"):
        event.validate()
