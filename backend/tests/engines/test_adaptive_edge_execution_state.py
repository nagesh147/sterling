from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.execution_state import (
    ExecutionLineage,
    ExecutionStateError,
    OrderConstructionState,
    ReconciliationState,
    SubmissionAttempt,
    SubmissionState,
    ExternalOrderState,
    validate_execution_transition,
)

UTC = timezone.utc


def test_order_construction_cannot_skip_from_ready_to_submitted_domain():
    with pytest.raises(ExecutionStateError, match="cross-domain"):
        validate_execution_transition(OrderConstructionState.READY, SubmissionState.SUBMITTED)


def test_unknown_submission_is_explicit_and_recoverable():
    validate_execution_transition(SubmissionState.NOT_SUBMITTED, SubmissionState.SUBMISSION_PENDING)
    validate_execution_transition(SubmissionState.SUBMISSION_PENDING, SubmissionState.SUBMISSION_UNKNOWN)
    validate_execution_transition(SubmissionState.SUBMISSION_UNKNOWN, SubmissionState.SUBMITTED)


def test_timeout_must_not_be_encoded_as_rejection():
    validate_execution_transition(SubmissionState.SUBMISSION_PENDING, SubmissionState.SUBMISSION_UNKNOWN)
    with pytest.raises(ExecutionStateError, match="forbidden transition"):
        validate_execution_transition(SubmissionState.SUBMISSION_UNKNOWN, SubmissionState.SUBMISSION_REJECTED)
    # The rejected transition is intentionally not the allowed recovery path
    # in this framework; a later authoritative observation is required.


def test_duplicate_partial_external_observation_is_allowed():
    validate_execution_transition(ExternalOrderState.OPEN, ExternalOrderState.PARTIALLY_FILLED)
    validate_execution_transition(ExternalOrderState.PARTIALLY_FILLED, ExternalOrderState.PARTIALLY_FILLED)


def test_reconciliation_conflict_is_explicit_state():
    validate_execution_transition(ReconciliationState.NOT_RECONCILED, ReconciliationState.RECONCILING)
    validate_execution_transition(ReconciliationState.RECONCILING, ReconciliationState.RECONCILIATION_EXCEPTION)
    validate_execution_transition(ReconciliationState.RECONCILIATION_EXCEPTION, ReconciliationState.RECONCILING)


def test_lineage_and_attempt_require_identity_and_timezone():
    lineage = ExecutionLineage("intent-1", "decision-1", "auth-1", "NIFTY", "policy-1", "exec-1")
    assert lineage.order_intent_id == "intent-1"

    attempt = SubmissionAttempt("attempt-1", "intent-1", "idem-1", datetime(2026, 8, 12, 10, 0, tzinfo=UTC))
    assert attempt.idempotency_key == "idem-1"

    with pytest.raises(ExecutionStateError, match="timezone-aware"):
        SubmissionAttempt("attempt-2", "intent-1", "idem-2", datetime(2026, 8, 12, 10, 0))
