"""A59 execution boundary primitives.

Separates authorization, immutable order intent, submission, acceptance and
confirmed fills. Provider execution behavior is deliberately not implemented.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ExecutionBoundaryError(ValueError):
    """Raised when an execution-boundary invariant is violated."""


class OrderLifecycleState(str, Enum):
    AUTHORIZED = "authorized"
    SUBMISSION_REJECTED = "submission_rejected"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    opportunity_id: str
    authorization_id: str
    sizing_id: str
    instrument_id: str
    direction: str
    quantity: int
    order_type: str
    decision_time_ms: int
    strategy_version: str
    execution_policy_version: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.intent_id, "intent_id"),
            (self.opportunity_id, "opportunity_id"),
            (self.authorization_id, "authorization_id"),
            (self.sizing_id, "sizing_id"),
            (self.instrument_id, "instrument_id"),
            (self.direction, "direction"),
            (self.order_type, "order_type"),
            (self.strategy_version, "strategy_version"),
            (self.execution_policy_version, "execution_policy_version"),
        ):
            if not value.strip():
                raise ExecutionBoundaryError(f"{name} must not be empty")
        if self.direction not in {"BUY", "SELL"}:
            raise ExecutionBoundaryError("direction must be BUY or SELL")
        if self.quantity <= 0:
            raise ExecutionBoundaryError("quantity must be positive")
        if self.decision_time_ms < 0:
            raise ExecutionBoundaryError("decision_time_ms must be non-negative")


@dataclass(frozen=True)
class OrderLifecycle:
    intent_id: str
    state: OrderLifecycleState
    submission_time_ms: Optional[int] = None
    acceptance_time_ms: Optional[int] = None
    cumulative_filled_quantity: int = 0

    def __post_init__(self) -> None:
        if not self.intent_id.strip():
            raise ExecutionBoundaryError("intent_id must not be empty")
        if self.cumulative_filled_quantity < 0:
            raise ExecutionBoundaryError("filled quantity must be non-negative")


def authorize_order(intent: OrderIntent, authorization_id: str) -> OrderLifecycle:
    if intent.authorization_id != authorization_id:
        raise ExecutionBoundaryError("order intent authorization identity mismatch")
    return OrderLifecycle(intent_id=intent.intent_id, state=OrderLifecycleState.AUTHORIZED)


def record_submission(
    lifecycle: OrderLifecycle,
    submission_time_ms: int,
    accepted: bool,
) -> OrderLifecycle:
    if lifecycle.state is not OrderLifecycleState.AUTHORIZED:
        raise ExecutionBoundaryError("only an authorized intent may be submitted")
    if submission_time_ms < 0:
        raise ExecutionBoundaryError("submission_time_ms must be non-negative")
    state = OrderLifecycleState.SUBMITTED if accepted else OrderLifecycleState.SUBMISSION_REJECTED
    return OrderLifecycle(
        intent_id=lifecycle.intent_id,
        state=state,
        submission_time_ms=submission_time_ms,
    )


def record_fill(
    intent: OrderIntent,
    lifecycle: OrderLifecycle,
    fill_quantity: int,
    fill_time_ms: int,
) -> OrderLifecycle:
    if lifecycle.intent_id != intent.intent_id:
        raise ExecutionBoundaryError("fill intent identity mismatch")
    if lifecycle.state not in {OrderLifecycleState.SUBMITTED, OrderLifecycleState.PARTIALLY_FILLED}:
        raise ExecutionBoundaryError("fills require a submitted order")
    if fill_quantity <= 0:
        raise ExecutionBoundaryError("fill quantity must be positive")
    if lifecycle.cumulative_filled_quantity + fill_quantity > intent.quantity:
        raise ExecutionBoundaryError("cumulative fills cannot exceed requested quantity")
    if lifecycle.submission_time_ms is not None and fill_time_ms < lifecycle.submission_time_ms:
        raise ExecutionBoundaryError("fill cannot precede submission")
    cumulative = lifecycle.cumulative_filled_quantity + fill_quantity
    state = OrderLifecycleState.FILLED if cumulative == intent.quantity else OrderLifecycleState.PARTIALLY_FILLED
    return OrderLifecycle(
        intent_id=intent.intent_id,
        state=state,
        submission_time_ms=lifecycle.submission_time_ms,
        acceptance_time_ms=lifecycle.acceptance_time_ms,
        cumulative_filled_quantity=cumulative,
    )
