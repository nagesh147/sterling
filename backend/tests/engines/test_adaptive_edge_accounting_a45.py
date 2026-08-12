from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.accounting_reconciliation import (
    AccountingLedger,
    AccountingReconciliationError,
    FillEvent,
    ReconciliationStatus,
    reconcile_fill_ids,
)

DT = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)


def make_fill(payload="fp-1"):
    return FillEvent(
        fill_id="fill-1",
        order_intent_id="intent-1",
        instrument_id="NIFTY",
        side="BUY",
        quantity=10.0,
        price=100.0,
        execution_time=DT,
        received_time=DT,
        provider_reference="provider-1",
        currency="INR",
        payload_fingerprint=payload,
    )


def test_fill_ingestion_is_idempotent():
    ledger = AccountingLedger()
    assert ledger.ingest_fill(make_fill()) is True
    assert ledger.ingest_fill(make_fill()) is False
    assert ledger.source_fill_ids() == ("fill-1",)


def test_conflicting_reuse_of_fill_identity_is_rejected():
    ledger = AccountingLedger()
    ledger.ingest_fill(make_fill())
    with pytest.raises(AccountingReconciliationError):
        ledger.ingest_fill(make_fill(payload="different"))


def test_reconciliation_reports_missing_internal_fills():
    result = reconcile_fill_ids(
        {"fill-1"},
        {"fill-1", "fill-2"},
        reconciliation_id="recon-1",
        as_of=DT,
    )
    assert result.status is ReconciliationStatus.MISMATCH
    assert result.mismatches == ("missing_internal:fill-2",)


def test_reconciliation_is_reconciled_when_identities_match():
    result = reconcile_fill_ids(
        {"fill-1", "fill-2"},
        {"fill-1", "fill-2"},
        reconciliation_id="recon-1",
        as_of=DT,
    )
    assert result.status is ReconciliationStatus.RECONCILED
    assert result.mismatches == ()


def test_fill_received_time_cannot_precede_execution_time():
    with pytest.raises(AccountingReconciliationError):
        FillEvent(
            fill_id="fill-1",
            order_intent_id="intent-1",
            instrument_id="NIFTY",
            side="BUY",
            quantity=10.0,
            price=100.0,
            execution_time=DT,
            received_time=datetime(2026, 8, 11, 9, 59, tzinfo=timezone.utc),
            provider_reference="provider-1",
            currency="INR",
            payload_fingerprint="fp-1",
        )
