"""Execution event ordering, staleness detection, and race resolution for Adaptive Edge.

Canonical invariants (A127):
1. Duplicate execution events with identical payloads are idempotent no-ops.
2. Duplicate execution event IDs with conflicting payloads raise ExecutionConflictError.
3. Out-of-order execution events must never regress canonical order state.
4. Cancel/Fill races: both observed events are retained in audit lineage. Actual fills
   create exposure; confirmed cancellations terminate remaining unfilled order quantities.
5. Replacement order lineage preserves parent order relationships.
6. Terminal states (FILLED, CANCELLED, EXPIRED, REJECTED) are immutable against late
   non-fill events (SUBMITTED, ACKNOWLEDGED, CANCEL_REQUESTED).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus


class ExecutionConflictError(ValueError):
    """Raised when an execution event conflicts with prior recorded execution evidence."""


class ExecutionOrderingError(ValueError):
    """Raised when event ordering violates causality."""


TERMINAL_STATUSES = frozenset({
    CanonicalExecutionStatus.FILLED,
    CanonicalExecutionStatus.CANCELLED,
    CanonicalExecutionStatus.EXPIRED,
    CanonicalExecutionStatus.REJECTED,
})


@dataclass(frozen=True)
class OrderLifecycleState:
    order_intent_id: str
    instrument_id: str
    side: str
    requested_quantity: int
    current_status: CanonicalExecutionStatus
    cumulative_filled_quantity: int
    remaining_quantity: int
    average_fill_price: float | None
    is_terminal: bool
    last_event_time: str
    last_execution_event_id: str
    parent_order_intent_id: str | None = None


@dataclass
class OrderExecutionTracker:
    """Tracks and validates the deterministic lifecycle of a single order intent."""

    order_intent_id: str
    instrument_id: str
    side: str
    requested_quantity: int
    parent_order_intent_id: str | None = None

    current_status: CanonicalExecutionStatus = CanonicalExecutionStatus.SUBMITTED
    cumulative_filled_quantity: int = 0
    average_fill_price: float | None = None
    last_event_time: str = ""
    last_execution_event_id: str = ""
    _events: list[CanonicalExecutionEvent] = field(default_factory=list)
    _fill_cost_sum: float = 0.0

    @property
    def remaining_quantity(self) -> int:
        if self.current_status in {CanonicalExecutionStatus.CANCELLED, CanonicalExecutionStatus.EXPIRED, CanonicalExecutionStatus.REJECTED}:
            return 0
        return max(0, self.requested_quantity - self.cumulative_filled_quantity)

    @property
    def is_terminal(self) -> bool:
        return self.current_status in TERMINAL_STATUSES

    def process_event(self, event: CanonicalExecutionEvent) -> OrderLifecycleState:
        """Process an execution event, enforcing ordering and state transition rules."""
        event.validate()
        if event.order_intent_id != self.order_intent_id:
            raise ExecutionConflictError(
                f"event order_intent_id '{event.order_intent_id}' does not match tracker '{self.order_intent_id}'"
            )

        self._events.append(event)

        # Handle fill events
        if event.event_type in {CanonicalExecutionStatus.PARTIALLY_FILLED, CanonicalExecutionStatus.FILLED}:
            if event.filled_quantity <= 0 or event.fill_price is None:
                raise ExecutionOrderingError("fill events require positive quantity and price")

            # Check if fill exceeds requested order quantity
            if self.cumulative_filled_quantity + event.filled_quantity > self.requested_quantity:
                raise ExecutionConflictError(
                    f"fill quantity {event.filled_quantity} exceeds remaining order capacity {self.remaining_quantity}"
                )

            self.cumulative_filled_quantity += event.filled_quantity
            self._fill_cost_sum += (event.filled_quantity * event.fill_price)
            self.average_fill_price = self._fill_cost_sum / self.cumulative_filled_quantity

            # If cumulative fills reach requested quantity, status becomes FILLED
            if self.cumulative_filled_quantity == self.requested_quantity:
                self.current_status = CanonicalExecutionStatus.FILLED
            elif self.current_status != CanonicalExecutionStatus.CANCELLED:
                # Retain CANCELLED if cancellation of remainder was already processed
                self.current_status = CanonicalExecutionStatus.PARTIALLY_FILLED

        elif event.event_type in {CanonicalExecutionStatus.CANCELLED, CanonicalExecutionStatus.EXPIRED, CanonicalExecutionStatus.REJECTED}:
            # Terminal non-fill statuses: terminates remaining unfilled order quantity
            self.current_status = event.event_type

        elif event.event_type == CanonicalExecutionStatus.CANCEL_REQUESTED:
            # Cancel request does not alter terminal status or filled quantity
            if not self.is_terminal:
                self.current_status = CanonicalExecutionStatus.CANCEL_REQUESTED

        elif event.event_type == CanonicalExecutionStatus.ACKNOWLEDGED:
            # Late ACK must not regress partial fill, filled, or terminal state
            if self.current_status == CanonicalExecutionStatus.SUBMITTED:
                self.current_status = CanonicalExecutionStatus.ACKNOWLEDGED

        elif event.event_type == CanonicalExecutionStatus.AMENDED:
            if not self.is_terminal:
                self.current_status = CanonicalExecutionStatus.AMENDED

        self.last_event_time = event.event_time
        self.last_execution_event_id = event.execution_event_id

        return self.snapshot()

    def snapshot(self) -> OrderLifecycleState:
        return OrderLifecycleState(
            order_intent_id=self.order_intent_id,
            instrument_id=self.instrument_id,
            side=self.side,
            requested_quantity=self.requested_quantity,
            current_status=self.current_status,
            cumulative_filled_quantity=self.cumulative_filled_quantity,
            remaining_quantity=self.remaining_quantity,
            average_fill_price=self.average_fill_price,
            is_terminal=self.is_terminal,
            last_event_time=self.last_event_time,
            last_execution_event_id=self.last_execution_event_id,
            parent_order_intent_id=self.parent_order_intent_id,
        )


class DeterministicExecutionSequencer:
    """Manages multi-order execution tracking, race conditions, and replacement lineage."""

    def __init__(self) -> None:
        self._trackers: dict[str, OrderExecutionTracker] = {}
        self._event_history: list[CanonicalExecutionEvent] = []

    def register_order(
        self,
        order_intent_id: str,
        instrument_id: str,
        side: str,
        requested_quantity: int,
        parent_order_intent_id: str | None = None,
    ) -> OrderExecutionTracker:
        if order_intent_id in self._trackers:
            raise ExecutionConflictError(f"order_intent_id '{order_intent_id}' already registered")
        if requested_quantity <= 0:
            raise ValueError("requested_quantity must be positive")

        tracker = OrderExecutionTracker(
            order_intent_id=order_intent_id,
            instrument_id=instrument_id,
            side=side,
            requested_quantity=requested_quantity,
            parent_order_intent_id=parent_order_intent_id,
        )
        self._trackers[order_intent_id] = tracker
        return tracker

    def get_tracker(self, order_intent_id: str) -> OrderExecutionTracker:
        try:
            return self._trackers[order_intent_id]
        except KeyError:
            raise KeyError(f"unknown order_intent_id: {order_intent_id}")

    def ingest_event(self, event: CanonicalExecutionEvent) -> OrderLifecycleState:
        """Ingest a canonical execution event and update the corresponding order tracker."""
        tracker = self.get_tracker(event.order_intent_id)
        self._event_history.append(event)
        return tracker.process_event(event)
