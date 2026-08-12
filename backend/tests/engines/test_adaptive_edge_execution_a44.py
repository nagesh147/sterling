from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.execution_reconciliation import (
    ExecutionReconciliationError,
    ExecutionState,
    FillEvent,
    OrderIntentRecord,
    append_fill,
    create_intent,
    validate_transition,
)

DT = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def intent(quantity=10.0):
    return OrderIntentRecord(
        intent_id="intent-1",
        authorization_id="auth-1",
        instrument_id="NIFTY",
        direction="BUY",
        requested_quantity=quantity,
        order_type="MARKET",
        decision_time=DT,
        intent_version="v1",
        idempotency_key="idem-1",
    )


def fill(fill_id, quantity):
    return FillEvent(fill_id, "intent-1", quantity, 100.0, DT)


def test_intent_starts_created_without_implying_submission():
    reconciliation = create_intent(intent())
    assert reconciliation.state is ExecutionState.CREATED
    assert reconciliation.cumulative_filled_quantity == 0


def test_partial_fill_is_derived_from_confirmed_fill_quantity():
    reconciliation = create_intent(intent())
    reconciliation = reconciliation.__class__(reconciliation.intent, ExecutionState.SUBMITTED, ())
    reconciliation = append_fill(reconciliation, fill("fill-1", 4.0))
    assert reconciliation.state is ExecutionState.PARTIALLY_FILLED
    assert reconciliation.cumulative_filled_quantity == 4.0
    assert reconciliation.remaining_quantity == 6.0


def test_full_fill_requires_requested_quantity():
    reconciliation = create_intent(intent())
    reconciliation = reconciliation.__class__(reconciliation.intent, ExecutionState.SUBMITTED, ())
    reconciliation = append_fill(reconciliation, fill("fill-1", 10.0))
    assert reconciliation.state is ExecutionState.FILLED
    assert reconciliation.remaining_quantity == 0


def test_overfill_is_rejected():
    reconciliation = create_intent(intent())
    reconciliation = reconciliation.__class__(reconciliation.intent, ExecutionState.SUBMITTED, ())
    with pytest.raises(ExecutionReconciliationError):
        append_fill(reconciliation, fill("fill-1", 11.0))


def test_duplicate_fill_identity_is_rejected():
    reconciliation = create_intent(intent())
    reconciliation = reconciliation.__class__(reconciliation.intent, ExecutionState.SUBMITTED, ())
    reconciliation = append_fill(reconciliation, fill("fill-1", 4.0))
    with pytest.raises(ExecutionReconciliationError):
        append_fill(reconciliation, fill("fill-1", 4.0))


def test_execution_state_transitions_are_explicit():
    validate_transition(ExecutionState.CREATED, ExecutionState.SUBMITTED)
    validate_transition(ExecutionState.SUBMITTED, ExecutionState.PARTIALLY_FILLED)
    validate_transition(ExecutionState.PARTIALLY_FILLED, ExecutionState.FILLED)
    with pytest.raises(ExecutionReconciliationError):
        validate_transition(ExecutionState.FILLED, ExecutionState.SUBMITTED)
