"""A43 decision, eligibility, authorization, and order-intent state domains.

The framework defines legal architectural transitions only. It does not
calculate EffectiveRisk, sizing, risk limits, or execution constraints.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AuthorizationStateError(ValueError):
    """Raised when an A43 state transition violates the contract."""


class DecisionState(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    EVALUATING = "EVALUATING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class EligibilityState(str, Enum):
    UNKNOWN = "UNKNOWN"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"


class RiskAuthorizationState(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"


class OrderIntentState(str, Enum):
    NOT_CREATED = "NOT_CREATED"
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class StateTransition:
    from_state: Enum
    to_state: Enum
    occurred_at: datetime
    reason: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise AuthorizationStateError("transition timestamp must be timezone-aware")
        if not self.reason.strip():
            raise AuthorizationStateError("transition reason must not be empty")


@dataclass(frozen=True)
class AuthorizationScope:
    instrument_id: str
    opportunity_id: str
    strategy_version: str
    account_scope: str
    side: str
    max_quantity: float | None
    valid_from: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        for name in ("instrument_id", "opportunity_id", "strategy_version", "account_scope", "side"):
            if not getattr(self, name).strip():
                raise AuthorizationStateError(f"{name} must not be empty")
        if self.valid_from.tzinfo is None or self.expires_at.tzinfo is None:
            raise AuthorizationStateError("authorization scope timestamps must be timezone-aware")
        if self.expires_at <= self.valid_from:
            raise AuthorizationStateError("authorization expiry must be after valid_from")
        if self.max_quantity is not None and self.max_quantity <= 0:
            raise AuthorizationStateError("max_quantity must be positive when supplied")


def validate_transition(from_state: Enum, to_state: Enum) -> None:
    """Validate only explicitly permitted architectural transitions."""
    if isinstance(from_state, DecisionState) and isinstance(to_state, DecisionState):
        allowed = {
            DecisionState.NOT_EVALUATED: {DecisionState.EVALUATING},
            DecisionState.EVALUATING: {DecisionState.ACCEPTED, DecisionState.REJECTED},
            DecisionState.ACCEPTED: {DecisionState.EXPIRED, DecisionState.SUPERSEDED},
            DecisionState.REJECTED: {DecisionState.SUPERSEDED},
            DecisionState.EXPIRED: set(),
            DecisionState.SUPERSEDED: set(),
        }
    elif isinstance(from_state, RiskAuthorizationState) and isinstance(to_state, RiskAuthorizationState):
        allowed = {
            RiskAuthorizationState.NOT_REQUESTED: {RiskAuthorizationState.PENDING},
            RiskAuthorizationState.PENDING: {RiskAuthorizationState.AUTHORIZED, RiskAuthorizationState.DENIED, RiskAuthorizationState.INVALID},
            RiskAuthorizationState.AUTHORIZED: {RiskAuthorizationState.EXPIRED, RiskAuthorizationState.REVOKED},
            RiskAuthorizationState.DENIED: set(),
            RiskAuthorizationState.EXPIRED: set(),
            RiskAuthorizationState.REVOKED: set(),
            RiskAuthorizationState.INVALID: set(),
        }
    elif isinstance(from_state, EligibilityState) and isinstance(to_state, EligibilityState):
        allowed = {
            EligibilityState.UNKNOWN: {EligibilityState.ELIGIBLE, EligibilityState.INELIGIBLE, EligibilityState.INVALID},
            EligibilityState.ELIGIBLE: {EligibilityState.EXPIRED, EligibilityState.INVALID},
            EligibilityState.INELIGIBLE: {EligibilityState.EXPIRED},
            EligibilityState.EXPIRED: set(),
            EligibilityState.INVALID: set(),
        }
    elif isinstance(from_state, OrderIntentState) and isinstance(to_state, OrderIntentState):
        allowed = {
            OrderIntentState.NOT_CREATED: {OrderIntentState.CREATED},
            OrderIntentState.CREATED: {OrderIntentState.SUBMITTED, OrderIntentState.CANCEL_REQUESTED, OrderIntentState.REJECTED, OrderIntentState.EXPIRED},
            OrderIntentState.SUBMITTED: {OrderIntentState.CANCEL_REQUESTED, OrderIntentState.EXPIRED},
            OrderIntentState.CANCEL_REQUESTED: {OrderIntentState.CANCELLED},
            OrderIntentState.CANCELLED: set(),
            OrderIntentState.REJECTED: set(),
            OrderIntentState.EXPIRED: set(),
        }
    else:
        raise AuthorizationStateError("cross-domain state transition is forbidden")

    if to_state not in allowed[from_state]:
        raise AuthorizationStateError(f"forbidden transition: {from_state.value} -> {to_state.value}")
