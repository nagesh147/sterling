from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.accounting_reconciliation import (
    AccountingLedger,
    AccountingReconciliationError,
    FillEvent,
    LedgerEntry,
    ReconciliationStatus,
    reconcile_fill_ids,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)


def fill(fill_id: str = "fill-1", *, fingerprint: str = "fp-1") -> FillEvent:
    return FillEvent(
        fill_id=fill_id,
        order_intent_id="intent-1",
        instrument_id="NIFTY-I",
        side="BUY",
        quantity=1,
        price=100.0,
        execution_time=T0,
        received_time=T0,
        provider_reference=f"provider-{fill_id}",
        currency="INR",
        payload_fingerprint=fingerprint,
    )


def test_fill_ingestion_is_idempotent():
    ledger = AccountingLedger()
    assert ledger.ingest_fill(fill())
    assert not ledger.ingest_fill(fill())
    assert ledger.source_fill_ids() == ("fill-1",)


def test_conflicting_reuse_of_fill_identity_is_rejected():
    ledger = AccountingLedger()
    ledger.ingest_fill(fill())
    with pytest.raises(AccountingReconciliationError, match="conflicting payload"):
        ledger.ingest_fill(fill(fingerprint="different"))


def test_ledger_entry_requires_source_provenance():
    with pytest.raises(AccountingReconciliationError, match="source events"):
        LedgerEntry("entry-1", (), "POSITION", "NIFTY-I", "INR", T0)


def test_reconciliation_reports_exact_identity_mismatches():
    result = reconcile_fill_ids({"a", "b"}, {"b", "c"}, reconciliation_id="recon-1", as_of=T0)
    assert result.status is ReconciliationStatus.MISMATCH
    assert result.mismatches == ("missing_internal:c", "missing_external:a")


def test_reconciliation_is_clean_when_fill_id_sets_match():
    result = reconcile_fill_ids({"a", "b"}, {"a", "b"}, reconciliation_id="recon-2", as_of=T0)
    assert result.status is ReconciliationStatus.RECONCILED
    assert result.mismatches == ()


def test_reconciliation_requires_timezone_aware_as_of():
    with pytest.raises(AccountingReconciliationError, match="timezone-aware"):
        reconcile_fill_ids(set(), set(), reconciliation_id="recon-3", as_of=datetime(2026, 8, 12, 10, 0))


def test_reconciliation_requires_explicit_identity():
    with pytest.raises(AccountingReconciliationError, match="reconciliation_id"):
        reconcile_fill_ids(set(), set(), reconciliation_id="", as_of=T0)


def test_fill_cannot_arrive_before_its_execution_time():
    with pytest.raises(AccountingReconciliationError, match="received_time"):
        FillEvent(
            fill_id="fill-1",
            order_intent_id="intent-1",
            instrument_id="NIFTY-I",
            side="BUY",
            quantity=1,
            price=100,
            execution_time=T0,
            received_time=T0.replace(hour=9),
            provider_reference="provider-1",
            currency="INR",
            payload_fingerprint="fp-1",
        )
