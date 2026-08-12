from datetime import datetime, timezone

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

DT = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def test_decision_transitions_are_explicit():
    validate_transition(DecisionState.NOT_EVALUATED, DecisionState.EVALUATING)
    validate_transition(DecisionState.EVALUATING, DecisionState.ACCEPTED)
    validate_transition(DecisionState.EVALUATING, DecisionState.REJECTED)


def test_cross_domain_transition_is_forbidden():
    with pytest.raises(AuthorizationStateError):
        validate_transition(DecisionState.ACCEPTED, RiskAuthorizationState.AUTHORIZED)


def test_invalid_risk_authorization_transition_is_rejected():
    with pytest.raises(AuthorizationStateError):
        validate_transition(RiskAuthorizationState.DENIED, RiskAuthorizationState.AUTHORIZED)


def test_order_intent_requires_explicit_lifecycle():
    validate_transition(OrderIntentState.NOT_CREATED, OrderIntentState.CREATED)
    validate_transition(OrderIntentState.CREATED, OrderIntentState.SUBMITTED)
    with pytest.raises(AuthorizationStateError):
        validate_transition(OrderIntentState.CANCELLED, OrderIntentState.SUBMITTED)


def test_authorization_scope_requires_temporal_validity():
    scope = AuthorizationScope(
        instrument_id="NIFTY",
        opportunity_id="opp-1",
        strategy_version="2.1.0",
        account_scope="research",
        side="BUY",
        max_quantity=None,
        valid_from=DT,
        expires_at=datetime(2026, 8, 11, 10, 5, tzinfo=timezone.utc),
    )
    assert scope.expires_at > scope.valid_from


def test_authorization_scope_rejects_non_positive_quantity():
    with pytest.raises(AuthorizationStateError):
        AuthorizationScope(
            instrument_id="NIFTY",
            opportunity_id="opp-1",
            strategy_version="2.1.0",
            account_scope="research",
            side="BUY",
            max_quantity=0,
            valid_from=DT,
            expires_at=datetime(2026, 8, 11, 10, 5, tzinfo=timezone.utc),
        )


def test_transition_record_requires_timezone_aware_timestamp_and_reason():
    StateTransition(DecisionState.EVALUATING, DecisionState.ACCEPTED, DT, "policy accepted")
    with pytest.raises(AuthorizationStateError):
        StateTransition(DecisionState.EVALUATING, DecisionState.ACCEPTED, datetime(2026, 8, 11, 10, 0), "accepted")
    with pytest.raises(AuthorizationStateError):
        StateTransition(DecisionState.EVALUATING, DecisionState.ACCEPTED, DT, "")
