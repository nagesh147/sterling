"""A44 execution/submission/fill/reconciliation boundary.

The module models execution state without inventing broker semantics, fill
prices, latency, slippage, order-type behavior, or provider-specific statuses.
Actual position quantity is derived only from confirmed fills.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ExecutionReconciliationError(ValueError):
    pass


class ExecutionState(str, Enum):
    NOT_CREATED = "NOT_CREATED"
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class OrderIntentRecord:
    intent_id: str
    authorization_id: str
    instrument_id: str
    direction: str
    requested_quantity: float
    order_type: str
    decision_time: datetime
    intent_version: str
    idempotency_key: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.intent_id, "intent_id"),
            (self.authorization_id, "authorization_id"),
            (self.instrument_id, "instrument_id"),
            (self.direction, "direction"),
            (self.order_type, "order_type"),
            (self.intent_version, "intent_version"),
            (self.idempotency_key, "idempotency_key"),
        ):
            if not value.strip():
                raise ExecutionReconciliationError(f"{name} must not be empty")
        if self.direction not in {"BUY", "SELL"}:
            raise ExecutionReconciliationError("direction must be BUY or SELL")
        if self.requested_quantity <= 0:
            raise ExecutionReconciliationError("requested quantity must be positive")
        _aware(self.decision_time, "decision time")


@dataclass(frozen=True)
class FillEvent:
    fill_id: str
    intent_id: str
    filled_quantity: float
    fill_price: float
    fill_time: datetime
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        for value, name in ((self.fill_id, "fill_id"), (self.intent_id, "intent_id")):
            if not value.strip():
                raise ExecutionReconciliationError(f"{name} must not be empty")
        if self.filled_quantity <= 0:
            raise ExecutionReconciliationError("filled quantity must be positive")
        if self.fill_price < 0:
            raise ExecutionReconciliationError("fill price must be non-negative")
        _aware(self.fill_time, "fill time")


@dataclass(frozen=True)
class ExecutionReconciliation:
    intent: OrderIntentRecord
    state: ExecutionState
    fills: tuple[FillEvent, ...]

    @property
    def cumulative_filled_quantity(self) -> float:
        return sum(fill.filled_quantity for fill in self.fills)

    @property
    def remaining_quantity(self) -> float:
        return self.intent.requested_quantity - self.cumulative_filled_quantity

    def __post_init__(self) -> None:
        ids = [fill.fill_id for fill in self.fills]
        if len(ids) != len(set(ids)):
            raise ExecutionReconciliationError("duplicate fill identity")
        if any(fill.intent_id != self.intent.intent_id for fill in self.fills):
            raise ExecutionReconciliationError("fill references a different order intent")
        if self.cumulative_filled_quantity > self.intent.requested_quantity + 1e-12:
            raise ExecutionReconciliationError("cumulative filled quantity exceeds requested quantity")
        if self.state is ExecutionState.PARTIALLY_FILLED and not (0 < self.cumulative_filled_quantity < self.intent.requested_quantity):
            raise ExecutionReconciliationError("PARTIALLY_FILLED requires a non-zero incomplete fill quantity")
        if self.state is ExecutionState.FILLED and abs(self.remaining_quantity) > 1e-12:
            raise ExecutionReconciliationError("FILLED requires cumulative fills to equal requested quantity")


def validate_transition(from_state: ExecutionState, to_state: ExecutionState) -> None:
    allowed = {
        ExecutionState.NOT_CREATED: {ExecutionState.CREATED},
        ExecutionState.CREATED: {ExecutionState.SUBMITTED, ExecutionState.SUBMISSION_REJECTED, ExecutionState.EXPIRED},
        ExecutionState.SUBMITTED: {ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED, ExecutionState.CANCEL_REQUESTED, ExecutionState.CANCELLED, ExecutionState.SUBMISSION_REJECTED, ExecutionState.EXPIRED},
        ExecutionState.SUBMISSION_REJECTED: set(),
        ExecutionState.PARTIALLY_FILLED: {ExecutionState.FILLED, ExecutionState.CANCEL_REQUESTED, ExecutionState.CANCELLED, ExecutionState.EXPIRED},
        ExecutionState.FILLED: set(),
        ExecutionState.CANCEL_REQUESTED: {ExecutionState.CANCELLED, ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED, ExecutionState.EXPIRED},
        ExecutionState.CANCELLED: set(),
        ExecutionState.EXPIRED: set(),
    }
    if to_state not in allowed[from_state]:
        raise ExecutionReconciliationError(f"forbidden execution transition: {from_state.value} -> {to_state.value}")


def append_fill(reconciliation: ExecutionReconciliation, fill: FillEvent) -> ExecutionReconciliation:
    """Append an immutable confirmed fill and derive the next architectural state."""
    if reconciliation.state not in {ExecutionState.SUBMITTED, ExecutionState.PARTIALLY_FILLED, ExecutionState.CANCEL_REQUESTED}:
        raise ExecutionReconciliationError("fills may only be attached to active submitted execution")
    if fill.intent_id != reconciliation.intent.intent_id:
        raise ExecutionReconciliationError("fill intent mismatch")
    if any(existing.fill_id == fill.fill_id for existing in reconciliation.fills):
        raise ExecutionReconciliationError("duplicate fill identity")
    fills = reconciliation.fills + (fill,)
    quantity = sum(item.filled_quantity for item in fills)
    if quantity > reconciliation.intent.requested_quantity + 1e-12:
        raise ExecutionReconciliationError("fill quantity exceeds requested quantity")
    next_state = ExecutionState.FILLED if abs(quantity - reconciliation.intent.requested_quantity) <= 1e-12 else ExecutionState.PARTIALLY_FILLED
    return ExecutionReconciliation(reconciliation.intent, next_state, fills)


def create_intent(intent: OrderIntentRecord) -> ExecutionReconciliation:
    return ExecutionReconciliation(intent, ExecutionState.CREATED, ())


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExecutionReconciliationError(f"{name} must be timezone-aware")
