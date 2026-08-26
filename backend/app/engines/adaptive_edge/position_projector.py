"""Deterministic position projection for Adaptive Edge.

Canonical invariants:
1. Position quantity changes ONLY from canonical execution evidence (FILLED, PARTIALLY_FILLED).
2. Non-fill events (SUBMITTED, ACKNOWLEDGED, CANCELLED, EXPIRED, etc.) do NOT change quantity.
3. Average entry price is derived deterministically:
       average_price = Σ(q_i * p_i) / Σ(q_i)
4. Partial entries, multiple fills, partial exits, cancelled remainders, and full flattening
   are deterministically projected.
5. Over-exit or non-positive price/quantity fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .e2e import PositionState
from .execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus


class PositionInvariantError(ValueError):
    """Raised when an execution event violates position state invariants."""


@dataclass(frozen=True)
class FillRecord:
    fill_id: str
    execution_event_id: str
    order_intent_id: str
    side: str  # "BUY" or "SELL"
    quantity: int
    price: float
    event_time: str
    evidence_class: str


class DeterministicPositionProjector:
    """Stateful, deterministic projector converting canonical execution events to PositionState."""

    def __init__(
        self,
        position_id: str,
        instrument_id: str,
        *,
        side: str = "BUY",
        order_side_map: Mapping[str, str] | Callable[[str], str] | None = None,
    ) -> None:
        if not position_id:
            raise ValueError("position_id is required")
        if not instrument_id:
            raise ValueError("instrument_id is required")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")

        self._position_id = position_id
        self._instrument_id = instrument_id
        self._initial_side = side
        self._order_side_map = order_side_map

        self._current_quantity: int = 0
        self._total_entry_quantity: int = 0
        self._total_entry_cost: float = 0.0
        self._total_exit_quantity: int = 0
        self._total_exit_value: float = 0.0
        self._realized_pnl: float = 0.0
        self._average_price: float = 0.0
        self._lifecycle_state: str = "FLAT"
        self._last_event_id: str = "initial"
        self._fills: list[FillRecord] = []
        self._state_history: list[PositionState] = []

    @property
    def position_id(self) -> str:
        return self._position_id

    @property
    def instrument_id(self) -> str:
        return self._instrument_id

    @property
    def current_quantity(self) -> int:
        return self._current_quantity

    @property
    def average_price(self) -> float:
        return self._average_price

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

    @property
    def lifecycle_state(self) -> str:
        return self._lifecycle_state

    @property
    def fills(self) -> tuple[FillRecord, ...]:
        return tuple(self._fills)

    @property
    def is_open(self) -> bool:
        return self._current_quantity > 0

    @property
    def is_flat(self) -> bool:
        return self._current_quantity == 0

    def _resolve_order_side(self, event: CanonicalExecutionEvent) -> str:
        if self._order_side_map is not None:
            if callable(self._order_side_map):
                return self._order_side_map(event.order_intent_id)
            if event.order_intent_id in self._order_side_map:
                return self._order_side_map[event.order_intent_id]
        # Default assumption: if position is empty, side is entry side.
        # If position is open and no map is provided, assume incoming fills with the same side add to position,
        # and opposing side reduces position.
        return self._initial_side

    def project(self, event: CanonicalExecutionEvent) -> PositionState:
        """Project a single canonical execution event into updated PositionState."""
        event.validate()
        self._last_event_id = event.execution_event_id

        is_fill = event.event_type in {
            CanonicalExecutionStatus.PARTIALLY_FILLED,
            CanonicalExecutionStatus.FILLED,
        }

        if not is_fill:
            # Non-fill events (ACKNOWLEDGED, CANCELLED, REJECTED, EXPIRED, etc.)
            # must not alter position quantity or average price.
            state = PositionState(
                position_id=self._position_id,
                instrument_id=self._instrument_id,
                quantity=self._current_quantity,
                average_price=self._average_price,
                lifecycle_state=self._lifecycle_state,
                source_execution_event_id=event.execution_event_id,
            )
            self._state_history.append(state)
            return state

        # Process fill event
        fill_qty = event.filled_quantity
        fill_price = event.fill_price
        if fill_qty <= 0:
            raise PositionInvariantError("fill quantity must be strictly positive")
        if fill_price is None or fill_price <= 0:
            raise PositionInvariantError("fill price must be strictly positive")

        event_side = self._resolve_order_side(event)
        is_entry = (event_side == self._initial_side)

        fill_record = FillRecord(
            fill_id=f"fill-{event.execution_event_id}",
            execution_event_id=event.execution_event_id,
            order_intent_id=event.order_intent_id,
            side=event_side,
            quantity=fill_qty,
            price=fill_price,
            event_time=event.event_time,
            evidence_class=event.evidence_class,
        )
        self._fills.append(fill_record)

        if is_entry:
            # Scaling in / entry fill
            self._total_entry_cost += (fill_qty * fill_price)
            self._total_entry_quantity += fill_qty
            self._current_quantity += fill_qty
            self._average_price = self._total_entry_cost / self._total_entry_quantity
            self._lifecycle_state = "OPEN"
        else:
            # Scaling out / exit fill
            if fill_qty > self._current_quantity:
                raise PositionInvariantError(
                    f"exit fill quantity ({fill_qty}) exceeds current open quantity ({self._current_quantity})"
                )

            # Realized PnL calculation
            if self._initial_side == "BUY":
                # Long position: sell price - avg buy price
                pnl = fill_qty * (fill_price - self._average_price)
            else:
                # Short position: avg sell price - buy price
                pnl = fill_qty * (self._average_price - fill_price)

            self._realized_pnl += pnl
            self._total_exit_quantity += fill_qty
            self._total_exit_value += (fill_qty * fill_price)
            self._current_quantity -= fill_qty

            if self._current_quantity == 0:
                self._lifecycle_state = "FLAT"
            else:
                self._lifecycle_state = "OPEN"

        state = PositionState(
            position_id=self._position_id,
            instrument_id=self._instrument_id,
            quantity=self._current_quantity,
            average_price=self._average_price,
            lifecycle_state=self._lifecycle_state,
            source_execution_event_id=event.execution_event_id,
        )
        self._state_history.append(state)
        return state

    def project_all(self, events: Sequence[CanonicalExecutionEvent]) -> PositionState:
        """Project a sequential stream of execution events deterministically."""
        state = None
        for event in events:
            state = self.project(event)
        if state is None:
            return PositionState(
                position_id=self._position_id,
                instrument_id=self._instrument_id,
                quantity=self._current_quantity,
                average_price=self._average_price,
                lifecycle_state=self._lifecycle_state,
                source_execution_event_id=self._last_event_id,
            )
        return state
