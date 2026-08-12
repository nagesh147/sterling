"""A44 execution/order state-machine framework.

This module deliberately contains no broker-specific order semantics, sizing,
price policy, retry policy, or fill assumptions. It provides only the typed
state domains and transition guards required by the A44 contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ExecutionStateError(ValueError):
    """Raised when an A44 invariant is violated."""


class OrderConstructionState(str, Enum):
    NOT_READY = "NOT_READY"
    READY = "READY"
    CONSTRUCTED = "CONSTRUCTED"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SubmissionState(str, Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMISSION_PENDING = "SUBMISSION_PENDING"
    SUBMITTED = "SUBMITTED"
    SUBMISSION_UNKNOWN = "SUBMISSION_UNKNOWN"
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED"
    SUBMISSION_CANCELLED = "SUBMISSION_CANCELLED"


class ExternalOrderState(str, Enum):
    UNKNOWN = "UNKNOWN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ReconciliationState(str, Enum):
    NOT_RECONCILED = "NOT_RECONCILED"
    RECONCILING = "RECONCILING"
    RECONCILED_OPEN = "RECONCILED_OPEN"
    RECONCILED_PARTIAL = "RECONCILED_PARTIAL"
    RECONCILED_FILLED = "RECONCILED_FILLED"
    RECONCILED_CANCELLED = "RECONCILED_CANCELLED"
    RECONCILED_REJECTED = "RECONCILED_REJECTED"
    RECONCILIATION_EXCEPTION = "RECONCILIATION_EXCEPTION"


@dataclass(frozen=True)
class ExecutionLineage:
    order_intent_id: str
    decision_id: str
    authorization_id: str
    instrument_id: str
    policy_version: str
    execution_contract_version: str

    def __post_init__(self) -> None:
        for name in (
            "order_intent_id", "decision_id", "authorization_id", "instrument_id",
            "policy_version", "execution_contract_version",
        ):
            if not getattr(self, name).strip():
                raise ExecutionStateError(f"{name} must not be empty")


@dataclass(frozen=True)
class SubmissionAttempt:
    submission_attempt_id: str
    order_intent_id: str
    idempotency_key: str
    created_at: datetime

    def __post_init__(self) -> None:
        for name in ("submission_attempt_id", "order_intent_id", "idempotency_key"):
            if not getattr(self, name).strip():
                raise ExecutionStateError(f"{name} must not be empty")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ExecutionStateError("created_at must be timezone-aware")


def validate_execution_transition(from_state: Enum, to_state: Enum) -> None:
    """Validate only contract-defined transitions inside one A44 state domain."""
    if isinstance(from_state, OrderConstructionState) and isinstance(to_state, OrderConstructionState):
        allowed = {
            OrderConstructionState.NOT_READY: {OrderConstructionState.READY, OrderConstructionState.INVALID},
            OrderConstructionState.READY: {OrderConstructionState.CONSTRUCTED, OrderConstructionState.INVALID, OrderConstructionState.EXPIRED},
            OrderConstructionState.CONSTRUCTED: {OrderConstructionState.EXPIRED, OrderConstructionState.CANCELLED},
            OrderConstructionState.INVALID: set(),
            OrderConstructionState.EXPIRED: set(),
            OrderConstructionState.CANCELLED: set(),
        }
    elif isinstance(from_state, SubmissionState) and isinstance(to_state, SubmissionState):
        allowed = {
            SubmissionState.NOT_SUBMITTED: {SubmissionState.SUBMISSION_PENDING},
            SubmissionState.SUBMISSION_PENDING: {
                SubmissionState.SUBMITTED,
                SubmissionState.SUBMISSION_UNKNOWN,
                SubmissionState.SUBMISSION_REJECTED,
            },
            SubmissionState.SUBMITTED: {SubmissionState.SUBMISSION_CANCELLED},
            SubmissionState.SUBMISSION_UNKNOWN: {
                SubmissionState.SUBMITTED,
                SubmissionState.SUBMISSION_REJECTED,
                SubmissionState.SUBMISSION_CANCELLED,
            },
            SubmissionState.SUBMISSION_REJECTED: set(),
            SubmissionState.SUBMISSION_CANCELLED: set(),
        }
    elif isinstance(from_state, ExternalOrderState) and isinstance(to_state, ExternalOrderState):
        allowed = {
            ExternalOrderState.UNKNOWN: {
                ExternalOrderState.ACKNOWLEDGED,
                ExternalOrderState.OPEN,
                ExternalOrderState.REJECTED,
                ExternalOrderState.EXPIRED,
            },
            ExternalOrderState.ACKNOWLEDGED: {ExternalOrderState.OPEN, ExternalOrderState.REJECTED, ExternalOrderState.EXPIRED},
            ExternalOrderState.OPEN: {
                ExternalOrderState.PARTIALLY_FILLED,
                ExternalOrderState.FILLED,
                ExternalOrderState.CANCEL_PENDING,
                ExternalOrderState.CANCELLED,
                ExternalOrderState.EXPIRED,
            },
            ExternalOrderState.PARTIALLY_FILLED: {
                ExternalOrderState.PARTIALLY_FILLED,
                ExternalOrderState.FILLED,
                ExternalOrderState.CANCEL_PENDING,
                ExternalOrderState.CANCELLED,
            },
            ExternalOrderState.FILLED: set(),
            ExternalOrderState.CANCEL_PENDING: {ExternalOrderState.CANCELLED, ExternalOrderState.PARTIALLY_FILLED, ExternalOrderState.FILLED},
            ExternalOrderState.CANCELLED: set(),
            ExternalOrderState.REJECTED: set(),
            ExternalOrderState.EXPIRED: set(),
        }
    elif isinstance(from_state, ReconciliationState) and isinstance(to_state, ReconciliationState):
        allowed = {
            ReconciliationState.NOT_RECONCILED: {ReconciliationState.RECONCILING},
            ReconciliationState.RECONCILING: {
                ReconciliationState.RECONCILED_OPEN,
                ReconciliationState.RECONCILED_PARTIAL,
                ReconciliationState.RECONCILED_FILLED,
                ReconciliationState.RECONCILED_CANCELLED,
                ReconciliationState.RECONCILED_REJECTED,
                ReconciliationState.RECONCILIATION_EXCEPTION,
            },
            ReconciliationState.RECONCILED_OPEN: {ReconciliationState.RECONCILING},
            ReconciliationState.RECONCILED_PARTIAL: {ReconciliationState.RECONCILING},
            ReconciliationState.RECONCILED_FILLED: set(),
            ReconciliationState.RECONCILED_CANCELLED: set(),
            ReconciliationState.RECONCILED_REJECTED: set(),
            ReconciliationState.RECONCILIATION_EXCEPTION: {ReconciliationState.RECONCILING},
        }
    else:
        raise ExecutionStateError("cross-domain execution transition is forbidden")

    if to_state not in allowed[from_state]:
        raise ExecutionStateError(f"forbidden transition: {from_state.value} -> {to_state.value}")
