import pytest

from app.engines.adaptive_edge.accounting_integrity import (
    AccountingIntegrityError,
    AccountingSourceEvent,
    DerivedEconomicEffect,
    append_source_event,
    require_correction_lineage,
    validate_effect_provenance,
)


def make_event(event_id: str = "fill-1", **overrides: object) -> AccountingSourceEvent:
    values = {
        "event_id": event_id,
        "source_system": "provider",
        "provider_reference": "provider-fill-1",
        "instrument_id": "NIFTY",
        "currency": "INR",
        "occurred_at_ms": 1_000,
        "policy_id": "accounting-policy",
        "policy_version": "1",
        "source_event_version": "1",
        "payload_fingerprint": "abc123",
    }
    values.update(overrides)
    return AccountingSourceEvent(**values)


def test_source_event_requires_currency_and_policy_provenance():
    with pytest.raises(AccountingIntegrityError):
        make_event(currency="")
    with pytest.raises(AccountingIntegrityError):
        make_event(policy_version="")


def test_derived_effect_requires_source_lineage_and_causal_time():
    event = make_event()
    effect = DerivedEconomicEffect("effect-1", "fill-1", "policy", "1", 1_001)

    assert validate_effect_provenance(event, effect) is effect

    with pytest.raises(AccountingIntegrityError):
        validate_effect_provenance(
            event,
            DerivedEconomicEffect("effect-2", "other-fill", "policy", "1", 1_001),
        )

    with pytest.raises(AccountingIntegrityError):
        validate_effect_provenance(
            event,
            DerivedEconomicEffect("effect-3", "fill-1", "policy", "1", 999),
        )


def test_reprocessing_identical_source_event_is_idempotent():
    event = make_event()
    ledger = append_source_event((), event)

    assert append_source_event(ledger, event) == ledger


def test_same_event_id_with_different_payload_is_rejected():
    event = make_event()
    ledger = append_source_event((), event)

    with pytest.raises(AccountingIntegrityError):
        append_source_event(
            ledger,
            make_event(payload_fingerprint="different"),
        )


def test_correction_preserves_original_event_and_uses_new_identity():
    original = make_event()
    corrected = make_event(
        event_id="fill-1-correction",
        provider_reference="provider-fill-1-correction",
        payload_fingerprint="corrected",
        source_event_version="2",
        supersedes_event_id="fill-1",
        occurred_at_ms=1_001,
    )

    assert require_correction_lineage(corrected, original) is corrected

    with pytest.raises(AccountingIntegrityError):
        require_correction_lineage(
            make_event(
                event_id="fill-1-correction-2",
                supersedes_event_id="wrong-fill",
                occurred_at_ms=1_001,
            ),
            original,
        )
