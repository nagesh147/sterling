import pytest

from app.engines.adaptive_edge.execution_adapter import (
    CanonicalExecutionEvent,
    CanonicalExecutionStatus,
)
from app.engines.adaptive_edge.position_projector import (
    DeterministicPositionProjector,
    PositionInvariantError,
)


def make_event(
    event_id: str,
    event_type: CanonicalExecutionStatus,
    qty: int = 0,
    price: float | None = None,
    order_id: str = "oi-1",
    timestamp: str = "2026-08-14T03:45:00+00:00",
) -> CanonicalExecutionEvent:
    return CanonicalExecutionEvent(
        execution_event_id=event_id,
        order_intent_id=order_id,
        event_type=event_type,
        event_time=timestamp,
        filled_quantity=qty,
        fill_price=price,
        evidence_class="OBSERVED",
    )


def test_initial_state_is_flat():
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE")
    assert projector.current_quantity == 0
    assert projector.average_price == 0.0
    assert projector.realized_pnl == 0.0
    assert projector.lifecycle_state == "FLAT"
    assert projector.is_flat is True
    assert projector.is_open is False


def test_partial_entry_creates_open_position():
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE", side="BUY")
    event = make_event("ex-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    state = projector.project(event)

    assert state.position_id == "pos-1"
    assert state.instrument_id == "NIFTY-CE"
    assert state.quantity == 40
    assert state.average_price == 100.0
    assert state.lifecycle_state == "OPEN"
    assert state.source_execution_event_id == "ex-1"
    assert projector.is_open is True


def test_multiple_entry_fills_calculate_weighted_average_price():
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE", side="BUY")
    e1 = make_event("ex-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    e2 = make_event("ex-2", CanonicalExecutionStatus.FILLED, qty=60, price=110.0)

    projector.project(e1)
    state = projector.project(e2)

    # (40 * 100 + 60 * 110) / 100 = (4000 + 6600) / 100 = 106.0
    assert state.quantity == 100
    assert state.average_price == 106.0
    assert state.lifecycle_state == "OPEN"
    assert state.source_execution_event_id == "ex-2"
    assert len(projector.fills) == 2


def test_non_fill_events_do_not_alter_position_exposure():
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE", side="BUY")
    e1 = make_event("ex-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    projector.project(e1)

    ack_event = make_event("ex-ack", CanonicalExecutionStatus.ACKNOWLEDGED)
    state = projector.project(ack_event)

    assert state.quantity == 40
    assert state.average_price == 100.0
    assert state.lifecycle_state == "OPEN"
    assert state.source_execution_event_id == "ex-ack"


def test_cancelled_remainder_does_not_exit_existing_position():
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE", side="BUY")
    # Requested 100, filled 40, remaining 60 cancelled
    fill_event = make_event("ex-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    cancel_event = make_event("ex-2", CanonicalExecutionStatus.CANCELLED)

    projector.project(fill_event)
    state = projector.project(cancel_event)

    assert state.quantity == 40
    assert state.average_price == 100.0
    assert state.lifecycle_state == "OPEN"
    assert projector.is_open is True


def test_partial_exit_and_realized_pnl():
    order_sides = {"oi-entry": "BUY", "oi-exit": "SELL"}
    projector = DeterministicPositionProjector(
        "pos-1", "NIFTY-CE", side="BUY", order_side_map=order_sides
    )

    # Enter 100 @ 100.0
    e1 = make_event("ex-1", CanonicalExecutionStatus.FILLED, qty=100, price=100.0, order_id="oi-entry")
    projector.project(e1)

    # Exit 40 @ 120.0 (PnL = 40 * (120 - 100) = 800.0)
    e2 = make_event("ex-2", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=120.0, order_id="oi-exit")
    state = projector.project(e2)

    assert state.quantity == 60
    assert state.average_price == 100.0
    assert state.lifecycle_state == "OPEN"
    assert projector.realized_pnl == 800.0


def test_full_flattening_transitions_to_flat():
    order_sides = {"oi-entry": "BUY", "oi-exit": "SELL"}
    projector = DeterministicPositionProjector(
        "pos-1", "NIFTY-CE", side="BUY", order_side_map=order_sides
    )

    # Enter 100 @ 100.0
    e1 = make_event("ex-1", CanonicalExecutionStatus.FILLED, qty=100, price=100.0, order_id="oi-entry")
    # Exit 100 @ 115.0
    e2 = make_event("ex-2", CanonicalExecutionStatus.FILLED, qty=100, price=115.0, order_id="oi-exit")

    projector.project(e1)
    state = projector.project(e2)

    assert state.quantity == 0
    assert state.lifecycle_state == "FLAT"
    assert projector.is_flat is True
    assert projector.realized_pnl == 1500.0


def test_over_exit_fails_closed():
    order_sides = {"oi-entry": "BUY", "oi-exit": "SELL"}
    projector = DeterministicPositionProjector(
        "pos-1", "NIFTY-CE", side="BUY", order_side_map=order_sides
    )

    # Enter 50 @ 100.0
    e1 = make_event("ex-1", CanonicalExecutionStatus.FILLED, qty=50, price=100.0, order_id="oi-entry")
    projector.project(e1)

    # Attempt to exit 60 (> 50)
    e2 = make_event("ex-2", CanonicalExecutionStatus.FILLED, qty=60, price=110.0, order_id="oi-exit")
    with pytest.raises(PositionInvariantError, match="exceeds current open quantity"):
        projector.project(e2)

    # Quantity remains untouched at 50
    assert projector.current_quantity == 50


def test_short_position_lifecycle():
    order_sides = {"oi-short-entry": "SELL", "oi-short-cover": "BUY"}
    projector = DeterministicPositionProjector(
        "pos-short", "NIFTY-PE", side="SELL", order_side_map=order_sides
    )

    # Sell to open 50 @ 200.0
    e1 = make_event("ex-1", CanonicalExecutionStatus.FILLED, qty=50, price=200.0, order_id="oi-short-entry")
    state1 = projector.project(e1)
    assert state1.quantity == 50
    assert state1.average_price == 200.0
    assert state1.lifecycle_state == "OPEN"

    # Buy to cover 50 @ 180.0 (PnL = 50 * (200 - 180) = +1000.0)
    e2 = make_event("ex-2", CanonicalExecutionStatus.FILLED, qty=50, price=180.0, order_id="oi-short-cover")
    state2 = projector.project(e2)
    assert state2.quantity == 0
    assert state2.lifecycle_state == "FLAT"
    assert projector.realized_pnl == 1000.0


def test_deterministic_stream_replay():
    events = [
        make_event("ex-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=30, price=100.0, order_id="e"),
        make_event("ex-2", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=70, price=110.0, order_id="e"),
        make_event("ex-3", CanonicalExecutionStatus.ACKNOWLEDGED, order_id="x"),
        make_event("ex-4", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=50, price=120.0, order_id="x"),
    ]
    order_map = {"e": "BUY", "x": "SELL"}

    # Sequential single-step projection
    p1 = DeterministicPositionProjector("pos-1", "NIFTY", side="BUY", order_side_map=order_map)
    for ev in events:
        p1.project(ev)

    # Stream replay projection
    p2 = DeterministicPositionProjector("pos-1", "NIFTY", side="BUY", order_side_map=order_map)
    p2.project_all(events)

    assert p1.current_quantity == p2.current_quantity == 50
    assert p1.average_price == p2.average_price == 107.0
    assert p1.realized_pnl == p2.realized_pnl == (50 * (120.0 - 107.0))
    assert p1.lifecycle_state == p2.lifecycle_state == "OPEN"
