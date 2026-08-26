"""A37 accounting event provenance and immutable-ledger primitives.

This module implements only the architectural integrity requirements already
specified by A37: stable source-event identity, explicit currency and policy
provenance, immutable correction lineage, and idempotent ingestion.

It deliberately does not define broker accounting, fees, contract multipliers,
settlement, valuation, P&L equations, or risk-consumption mathematics.
"""
from __future__ import annotations

from dataclasses import dataclass


class AccountingIntegrityError(ValueError):
    """Raised when accounting provenance or event-ledger invariants fail."""


@dataclass(frozen=True)
class AccountingSourceEvent:
    """Immutable canonical representation of an economic source event."""

    event_id: str
    source_system: str
    provider_reference: str
    instrument_id: str
    currency: str
    occurred_at_ms: int
    policy_id: str
    policy_version: str
    source_event_version: str
    payload_fingerprint: str
    supersedes_event_id: str | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.event_id, "event_id"),
            (self.source_system, "source_system"),
            (self.provider_reference, "provider_reference"),
            (self.instrument_id, "instrument_id"),
            (self.currency, "currency"),
            (self.policy_id, "policy_id"),
            (self.policy_version, "policy_version"),
            (self.source_event_version, "source_event_version"),
            (self.payload_fingerprint, "payload_fingerprint"),
        ):
            if not value.strip():
                raise AccountingIntegrityError(f"{name} must not be empty")
        if self.occurred_at_ms < 0:
            raise AccountingIntegrityError("occurred_at_ms must be non-negative")
        if self.supersedes_event_id == self.event_id:
            raise AccountingIntegrityError("an event cannot supersede itself")


@dataclass(frozen=True)
class DerivedEconomicEffect:
    """Versioned derived effect with mandatory source-event provenance."""

    effect_id: str
    source_event_id: str
    derivation_policy_id: str
    derivation_policy_version: str
    derived_at_ms: int

    def __post_init__(self) -> None:
        for value, name in (
            (self.effect_id, "effect_id"),
            (self.source_event_id, "source_event_id"),
            (self.derivation_policy_id, "derivation_policy_id"),
            (self.derivation_policy_version, "derivation_policy_version"),
        ):
            if not value.strip():
                raise AccountingIntegrityError(f"{name} must not be empty")
        if self.derived_at_ms < 0:
            raise AccountingIntegrityError("derived_at_ms must be non-negative")


def validate_effect_provenance(
    event: AccountingSourceEvent,
    effect: DerivedEconomicEffect,
) -> DerivedEconomicEffect:
    """Require a derived effect to reference an existing source event causally."""
    if effect.source_event_id != event.event_id:
        raise AccountingIntegrityError("derived effect must reference its source event")
    if effect.derived_at_ms < event.occurred_at_ms:
        raise AccountingIntegrityError("derived effect cannot precede its source event")
    return effect


def append_source_event(
    ledger: tuple[AccountingSourceEvent, ...],
    event: AccountingSourceEvent,
) -> tuple[AccountingSourceEvent, ...]:
    """Append an event idempotently while rejecting identity conflicts."""
    for existing in ledger:
        if existing.event_id != event.event_id:
            continue
        if existing == event:
            return ledger
        raise AccountingIntegrityError(
            f"source event identity conflict: {event.event_id}"
        )
    return (*ledger, event)


def require_correction_lineage(
    corrected_event: AccountingSourceEvent,
    original_event: AccountingSourceEvent,
) -> AccountingSourceEvent:
    """Require corrections to preserve the original event rather than replace it."""
    if corrected_event.supersedes_event_id != original_event.event_id:
        raise AccountingIntegrityError("correction must reference the original event")
    if corrected_event.event_id == original_event.event_id:
        raise AccountingIntegrityError("correction requires a distinct event identity")
    if corrected_event.occurred_at_ms < original_event.occurred_at_ms:
        raise AccountingIntegrityError("correction cannot precede the original event")
    return corrected_event
