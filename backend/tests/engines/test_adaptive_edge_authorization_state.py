from datetime import datetime, timedelta, timezone

import pytest

from app.engines.adaptive_edge.authorization_state import (
    AuthorizationScope,
    AuthorizationStateError,
    DecisionState,
    EligibilityState,
    OrderIntentState,
    RiskAuthorizationState,
    StateTransition,
    validate_transition,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


def test_decision_transition_requires_explicit_path():
    validate_transition(DecisionState.NOT_EVALUATED, DecisionState.EVALUATING)
    validate_transition(DecisionState.EVALUATING, DecisionState.ACCEPTED)
    with pytest.raises(AuthorizationStateError, match="forbidden transition"):
        validate_transition(DecisionState.NOT_EVALUATED, DecisionState.ACCEPTED)


def test_authorization_lifecycle_is_explicit():
    validate_transition(RiskAuthorizationState.NOT_REQUESTED, RiskAuthorizationState.PENDING)
    validate_transition(RiskAuthorizationState.PENDING, RiskAuthorizationState.AUTHORIZED)
    validate_transition(RiskAuthorizationState.AUTHORIZED, RiskAuthorizationState.REVOKED)
    with pytest.raises(AuthorizationStateError):
        validate_transition(RiskAuthorizationState.DENIED, RiskAuthorizationState.AUTHORIZED)


def test_cross_domain_transition_is_forbidden():
    with pytest.raises(AuthorizationStateError, match="cross-domain"):
        validate_transition(DecisionState.ACCEPTED, OrderIntentState.SUBMITTED)


def test_unknown_eligibility_cannot_skip_to_order_intent():
    with pytest.raises(AuthorizationStateError):
        validate_transition(EligibilityState.UNKNOWN, OrderIntentState.CREATED)


def test_authorization_scope_requires_positive_explicit_quantity_when_supplied():
    with pytest.raises(AuthorizationStateError, match="max_quantity"):
        AuthorizationScope("NIFTY", "opp-1", "v1", "acct-1", "BUY", 0, T0, T0 + timedelta(minutes=5))


def test_transition_requires_timezone_aware_timestamp():
    with pytest.raises(AuthorizationStateError, match="timezone-aware"):
        StateTransition(DecisionState.NOT_EVALUATED, DecisionState.EVALUATING, datetime(2026, 8, 12, 10, 0), "start")
