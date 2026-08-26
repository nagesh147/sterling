"""A45 structural execution/accounting reconciliation primitives.

This module deliberately does not invent instrument multipliers, fees,
settlement rules, valuation policy, or risk-consumption equations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AccountingReconciliationError(ValueError):
    """Raised when an A45 accounting invariant is violated."""


class ReconciliationStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    EVALUATING = "EVALUATING"
    RECONCILED = "RECONCILED"
    MISMATCH = "MISMATCH"
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FillEvent:
    fill_id: str
    order_intent_id: str
    instrument_id: str
    side: str
    quantity: float
    price: float
    execution_time: datetime
    received_time: datetime
    provider_reference: str
    currency: str
    payload_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "fill_id",
            "order_intent_id",
            "instrument_id",
            "side",
            "provider_reference",
            "currency",
            "payload_fingerprint",
        ):
            if not getattr(self, name).strip():
                raise AccountingReconciliationError(f"{name} must not be empty")
        if self.quantity <= 0:
            raise AccountingReconciliationError("fill quantity must be positive")
        if self.price < 0:
            raise AccountingReconciliationError("fill price cannot be negative")
        if self.execution_time.tzinfo is None or self.received_time.tzinfo is None:
            raise AccountingReconciliationError("fill timestamps must be timezone-aware")
        if self.received_time < self.execution_time:
            raise AccountingReconciliationError("received_time cannot precede execution_time")


@dataclass(frozen=True)
class LedgerEntry:
    ledger_entry_id: str
    source_event_ids: tuple[str, ...]
    entry_type: str
    instrument_id: str
    currency: str
    created_at: datetime
    quantity: float | None = None
    value: float | None = None
    policy_version: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not self.ledger_entry_id.strip() or not self.source_event_ids:
            raise AccountingReconciliationError("ledger entry requires identity and source events")
        if not self.entry_type.strip() or not self.instrument_id.strip() or not self.currency.strip():
            raise AccountingReconciliationError("ledger entry requires explicit semantic identity")
        if self.created_at.tzinfo is None:
            raise AccountingReconciliationError("ledger timestamp must be timezone-aware")


@dataclass(frozen=True)
class PositionSnapshot:
    instrument_id: str
    as_of: datetime
    source_fill_ids: tuple[str, ...]
    net_quantity: float

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or not self.source_fill_ids:
            raise AccountingReconciliationError("position snapshot requires instrument and source fills")
        if self.as_of.tzinfo is None:
            raise AccountingReconciliationError("position snapshot timestamp must be timezone-aware")


@dataclass(frozen=True)
class ReconciliationResult:
    reconciliation_id: str
    as_of: datetime
    status: ReconciliationStatus
    mismatches: tuple[str, ...] = ()
    source_versions: tuple[str, ...] = ()


@dataclass
class AccountingLedger:
    """Idempotent fill ledger; economic interpretation remains downstream."""

    fills: dict[str, FillEvent] = field(default_factory=dict)
    entries: dict[str, LedgerEntry] = field(default_factory=dict)

    def ingest_fill(self, fill: FillEvent) -> bool:
        """Record a fill once; reject a conflicting reuse of the same identity."""
        existing = self.fills.get(fill.fill_id)
        if existing is None:
            self.fills[fill.fill_id] = fill
            return True
        if existing == fill:
            return False
        raise AccountingReconciliationError(
            f"fill_id {fill.fill_id!r} was reused with a conflicting payload"
        )

    def add_entry(self, entry: LedgerEntry) -> bool:
        existing = self.entries.get(entry.ledger_entry_id)
        if existing is None:
            self.entries[entry.ledger_entry_id] = entry
            return True
        if existing == entry:
            return False
        raise AccountingReconciliationError(
            f"ledger_entry_id {entry.ledger_entry_id!r} was reused with conflicting content"
        )

    def source_fill_ids(self) -> tuple[str, ...]:
        return tuple(self.fills)


def reconcile_fill_ids(
    internal_fill_ids: set[str],
    external_fill_ids: set[str],
    *,
    reconciliation_id: str,
    as_of: datetime,
) -> ReconciliationResult:
    """Compare identities only; no provider-specific accounting semantics are inferred."""
    if not reconciliation_id.strip():
        raise AccountingReconciliationError("reconciliation_id must not be empty")
    if as_of.tzinfo is None:
        raise AccountingReconciliationError("reconciliation timestamp must be timezone-aware")
    missing_internal = sorted(external_fill_ids - internal_fill_ids)
    missing_external = sorted(internal_fill_ids - external_fill_ids)
    mismatches = tuple(
        [f"missing_internal:{fill_id}" for fill_id in missing_internal]
        + [f"missing_external:{fill_id}" for fill_id in missing_external]
    )
    status = ReconciliationStatus.RECONCILED if not mismatches else ReconciliationStatus.MISMATCH
    return ReconciliationResult(
        reconciliation_id=reconciliation_id,
        as_of=as_of,
        status=status,
        mismatches=mismatches,
    )
