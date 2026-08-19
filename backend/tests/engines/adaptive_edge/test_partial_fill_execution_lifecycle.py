from __future__ import annotations

import pytest

from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus
from app.engines.adaptive_edge.position_projector import DeterministicPositionProjector, PositionInvariantError


def event(event_id: str, side: str, quantity: int, price: float) -> CanonicalExecutionEvent:
    return CanonicalExecutionEvent(
        execution_event_id=event_id,
        order_intent_id=f"intent-{side}",
        event_type=CanonicalExecutionStatus.PARTIALLY_FILLED if quantity < 25 else CanonicalExecutionStatus.FILLED,
        event_time=f"2026-08-19T03:45:{int(event_id[-1]):02d}Z",
        filled_quantity=quantity,
        fill_price=price,
        evidence_class="OBSERVED",
    )


def test_partial_entry_then_completion_has_weighted_average():
    projector = DeterministicPositionProjector("p1", "NIFTY-CE", side="BUY")
    first = projector.project(event("e1", "BUY", 10, 100.0))
    second = projector.project(event("e2", "BUY", 15, 110.0))
    assert first.quantity == 10
    assert second.quantity == 25
    assert second.average_price == pytest.approx(106.0)


def test_partial_exit_realizes_pnl_and_full_exit_flattens():
    projector = DeterministicPositionProjector("p1", "NIFTY-CE", side="BUY")
    projector.project(event("e1", "BUY", 25, 100.0))
    # Explicit opposing-side mapping is required; otherwise the projector cannot infer an exit.
    projector._order_side_map = {"intent-SELL": "SELL"}
    partial = projector.project(event("e2", "SELL", 10, 110.0))
    assert partial.quantity == 15
    assert projector.realized_pnl == pytest.approx(100.0)
    final = projector.project(event("e3", "SELL", 15, 105.0))
    assert final.quantity == 0
    assert final.lifecycle_state == "FLAT"
    assert projector.realized_pnl == pytest.approx(175.0)


def test_over_exit_is_rejected_without_mutating_position():
    projector = DeterministicPositionProjector("p1", "NIFTY-CE", side="BUY", order_side_map={"intent-BUY": "BUY", "intent-SELL": "SELL"})
    projector.project(event("e1", "BUY", 10, 100.0))
    with pytest.raises(PositionInvariantError):
        projector.project(event("e2", "SELL", 11, 110.0))
    assert projector.current_quantity == 10


def test_non_fill_does_not_mutate_position():
    projector = DeterministicPositionProjector("p1", "NIFTY-CE", side="BUY")
    projector.project(event("e1", "BUY", 10, 100.0))
    non_fill = CanonicalExecutionEvent(
        execution_event_id="e2",
        order_intent_id="intent-BUY",
        event_type=CanonicalExecutionStatus.CANCELLED,
        event_time="2026-08-19T03:46:00Z",
        filled_quantity=0,
        fill_price=None,
        evidence_class="OBSERVED",
    )
    state = projector.project(non_fill)
    assert state.quantity == 10
    assert state.average_price == pytest.approx(100.0)
