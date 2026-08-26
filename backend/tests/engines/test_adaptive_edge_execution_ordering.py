import pytest

from app.engines.adaptive_edge.execution_adapter import (
    CanonicalExecutionEvent,
    CanonicalExecutionStatus,
)
from app.engines.adaptive_edge.execution_ordering import (
    DeterministicExecutionSequencer,
    ExecutionConflictError,
    ExecutionOrderingError,
)


def make_event(
    event_id: str,
    order_id: str,
    event_type: CanonicalExecutionStatus,
    qty: int = 0,
    price: float | None = None,
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


def test_order_normal_lifecycle_progression():
    sequencer = DeterministicExecutionSequencer()
    sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 100)

    # 1. Acknowledged
    e1 = make_event("ex-1", "oi-1", CanonicalExecutionStatus.ACKNOWLEDGED)
    s1 = sequencer.ingest_event(e1)
    assert s1.current_status is CanonicalExecutionStatus.ACKNOWLEDGED
    assert s1.cumulative_filled_quantity == 0
    assert s1.remaining_quantity == 100

    # 2. Partial fill (40 @ 100.0)
    e2 = make_event("ex-2", "oi-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    s2 = sequencer.ingest_event(e2)
    assert s2.current_status is CanonicalExecutionStatus.PARTIALLY_FILLED
    assert s2.cumulative_filled_quantity == 40
    assert s2.remaining_quantity == 60
    assert s2.average_fill_price == 100.0

    # 3. Final fill (60 @ 110.0)
    e3 = make_event("ex-3", "oi-1", CanonicalExecutionStatus.FILLED, qty=60, price=110.0)
    s3 = sequencer.ingest_event(e3)
    assert s3.current_status is CanonicalExecutionStatus.FILLED
    assert s3.cumulative_filled_quantity == 100
    assert s3.remaining_quantity == 0
    assert s3.average_fill_price == 106.0
    assert s3.is_terminal is True


def test_out_of_order_late_acknowledgement_does_not_regress_filled_state():
    sequencer = DeterministicExecutionSequencer()
    sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 50)

    # Immediate fill
    e_fill = make_event("ex-fill", "oi-1", CanonicalExecutionStatus.FILLED, qty=50, price=120.0)
    s_fill = sequencer.ingest_event(e_fill)
    assert s_fill.current_status is CanonicalExecutionStatus.FILLED

    # Late-arriving acknowledgement must not regress state
    e_late_ack = make_event("ex-ack", "oi-1", CanonicalExecutionStatus.ACKNOWLEDGED)
    s_late = sequencer.ingest_event(e_late_ack)
    assert s_late.current_status is CanonicalExecutionStatus.FILLED
    assert s_late.cumulative_filled_quantity == 50


def test_out_of_order_late_acknowledgement_does_not_regress_partial_fill():
    sequencer = DeterministicExecutionSequencer()
    sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 100)

    # Partial fill
    e_partial = make_event("ex-p", "oi-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    sequencer.ingest_event(e_partial)

    # Late ack
    e_late_ack = make_event("ex-ack", "oi-1", CanonicalExecutionStatus.ACKNOWLEDGED)
    s_late = sequencer.ingest_event(e_late_ack)
    assert s_late.current_status is CanonicalExecutionStatus.PARTIALLY_FILLED
    assert s_late.cumulative_filled_quantity == 40


def test_overfill_fails_closed():
    sequencer = DeterministicExecutionSequencer()
    sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 50)

    # Attempt fill of 60 (> 50)
    e = make_event("ex-over", "oi-1", CanonicalExecutionStatus.FILLED, qty=60, price=100.0)
    with pytest.raises(ExecutionConflictError, match="exceeds remaining order capacity"):
        sequencer.ingest_event(e)


def test_cancel_fill_race_resolution():
    sequencer = DeterministicExecutionSequencer()
    sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 100)

    # Cancel requested
    e_cancel_req = make_event("ex-cr", "oi-1", CanonicalExecutionStatus.CANCEL_REQUESTED)
    s_cr = sequencer.ingest_event(e_cancel_req)
    assert s_cr.current_status is CanonicalExecutionStatus.CANCEL_REQUESTED

    # Fill executed before cancel took effect at exchange (40 @ 100.0)
    e_fill = make_event("ex-fill", "oi-1", CanonicalExecutionStatus.PARTIALLY_FILLED, qty=40, price=100.0)
    s_fill = sequencer.ingest_event(e_fill)
    assert s_fill.current_status is CanonicalExecutionStatus.PARTIALLY_FILLED
    assert s_fill.cumulative_filled_quantity == 40

    # Broker confirms cancellation of remainder
    e_cancel = make_event("ex-can", "oi-1", CanonicalExecutionStatus.CANCELLED)
    s_cancel = sequencer.ingest_event(e_cancel)
    assert s_cancel.current_status is CanonicalExecutionStatus.CANCELLED
    assert s_cancel.cumulative_filled_quantity == 40
    assert s_cancel.is_terminal is True


def test_replacement_order_preserves_parent_lineage():
    sequencer = DeterministicExecutionSequencer()
    parent_tracker = sequencer.register_order("oi-parent", "NIFTY-CE", "BUY", 100)
    child_tracker = sequencer.register_order(
        "oi-child", "NIFTY-CE", "BUY", 100, parent_order_intent_id="oi-parent"
    )

    assert child_tracker.parent_order_intent_id == "oi-parent"
    child_snap = child_tracker.snapshot()
    assert child_snap.parent_order_intent_id == "oi-parent"


def test_duplicate_order_registration_fails_closed():
    sequencer = DeterministicExecutionSequencer()
    sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 50)
    with pytest.raises(ExecutionConflictError, match="already registered"):
        sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 50)


def test_mismatched_order_intent_in_event_fails():
    sequencer = DeterministicExecutionSequencer()
    tracker = sequencer.register_order("oi-1", "NIFTY-CE", "BUY", 50)
    e_mismatch = make_event("ex-m", "oi-OTHER", CanonicalExecutionStatus.ACKNOWLEDGED)
    with pytest.raises(ExecutionConflictError, match="does not match tracker"):
        tracker.process_event(e_mismatch)
