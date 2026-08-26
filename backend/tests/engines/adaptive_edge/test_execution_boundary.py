import pytest

from app.engines.adaptive_edge.execution_boundary import (
    ExecutionBoundaryError,
    OrderIntent,
    OrderLifecycleState,
    authorize_order,
    record_fill,
    record_submission,
)


def intent(**overrides):
    values = dict(
        intent_id="intent-1",
        opportunity_id="opp-1",
        authorization_id="auth-1",
        sizing_id="size-1",
        instrument_id="NIFTY-1",
        direction="BUY",
        quantity=10,
        order_type="MARKET",
        decision_time_ms=100,
        strategy_version="strategy-1",
        execution_policy_version="exec-1",
    )
    values.update(overrides)
    return OrderIntent(**values)


def test_authorization_identity_is_required():
    with pytest.raises(ExecutionBoundaryError):
        authorize_order(intent(), "auth-2")


def test_submission_requires_authorized_intent():
    lifecycle = authorize_order(intent(), "auth-1")
    result = record_submission(lifecycle, 110, accepted=True)
    assert result.state is OrderLifecycleState.SUBMITTED


def test_rejected_submission_is_not_execution():
    lifecycle = authorize_order(intent(), "auth-1")
    result = record_submission(lifecycle, 110, accepted=False)
    assert result.state is OrderLifecycleState.SUBMISSION_REJECTED


def test_fill_requires_submitted_order():
    lifecycle = authorize_order(intent(), "auth-1")
    with pytest.raises(ExecutionBoundaryError):
        record_fill(intent(), lifecycle, 1, 120)


def test_partial_fill_does_not_equal_full_fill():
    order = intent(quantity=10)
    submitted = record_submission(authorize_order(order, "auth-1"), 110, True)
    result = record_fill(order, submitted, 4, 120)
    assert result.state is OrderLifecycleState.PARTIALLY_FILLED
    assert result.cumulative_filled_quantity == 4


def test_final_fill_transitions_to_filled():
    order = intent(quantity=10)
    submitted = record_submission(authorize_order(order, "auth-1"), 110, True)
    partial = record_fill(order, submitted, 4, 120)
    result = record_fill(order, partial, 6, 130)
    assert result.state is OrderLifecycleState.FILLED
    assert result.cumulative_filled_quantity == 10


def test_overfill_is_rejected():
    order = intent(quantity=10)
    submitted = record_submission(authorize_order(order, "auth-1"), 110, True)
    with pytest.raises(ExecutionBoundaryError):
        record_fill(order, submitted, 11, 120)


def test_fill_cannot_precede_submission():
    order = intent()
    submitted = record_submission(authorize_order(order, "auth-1"), 110, True)
    with pytest.raises(ExecutionBoundaryError):
        record_fill(order, submitted, 1, 109)
