"""Composed T4/T5 adapters. Not isolated fixtures. No F-114 math."""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.e2e import DecisionEligibility
from app.engines.adaptive_edge.e2e_adapters import (
    BarFeatureBuilder,
    ComposedRiskAuthorizer,
    ExplicitGrossEdge,
    IdentityPredictionBinder,
    ListedInstrumentSelector,
    RiskAuthorizationError,
)
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.feature_engine import FeatureStatus
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.instrument_selection import (
    InstrumentSelectionError,
    ListedOptionCandidate,
)


ISSUED_AT = "2026-08-17T03:45:00+00:00"
AVAILABLE_AT = "2026-08-17T03:44:00+00:00"


def _decision(*, eligible: bool = True) -> DecisionEligibility:
    return DecisionEligibility(
        eligible=eligible,
        reason="entry_conjunction_passed" if eligible else "entry_conjunction_failed",
        decision_id="DEC-SNAP-1",
        snapshot_id="SNAP-1",
        prediction_id="PRED-1",
        opportunity_id="OPP-1",
    )


def _risk(*, state: RiskState = RiskState.AUTHORIZED, authorized_risk: float = 5000.0) -> RiskAuthorization:
    return RiskAuthorization(
        opportunity_id="opp-e2e",
        authorized_risk=authorized_risk,
        risk_state=state,
        policy_version="risk-v1",
        issued_at=ISSUED_AT,
    )


def _chain() -> tuple[ListedOptionCandidate, ...]:
    return (
        ListedOptionCandidate("NIFTY26AUG24600CE", "CE", 24600.0, "2026-08-27", 50.0, AVAILABLE_AT),
        ListedOptionCandidate("NIFTY26AUG24400CE", "CE", 24400.0, "2026-08-27", 90.0, AVAILABLE_AT),
        ListedOptionCandidate("NIFTY26AUG24500CE", "CE", 24500.0, "2026-08-27", 90.0, AVAILABLE_AT),
        ListedOptionCandidate("NIFTY26AUG24500PE", "PE", 24500.0, "2026-08-27", 120.0, AVAILABLE_AT),
    )


def test_composed_authorizer_binds_granted_ceiling_to_decision_identity():
    authorization = ComposedRiskAuthorizer(_risk()).authorize(_decision())
    assert authorization.intent_id == "AUTH-DEC-SNAP-1"
    assert authorization.decision_id == "DEC-SNAP-1"
    assert authorization.opportunity_id == "OPP-1"
    assert authorization.authorized_risk == 5000.0
    assert authorization.issued_at == ISSUED_AT


def test_composed_authorizer_rejects_ineligible_decision():
    with pytest.raises(RiskAuthorizationError, match="ineligible"):
        ComposedRiskAuthorizer(_risk()).authorize(_decision(eligible=False))


def test_composed_authorizer_rejects_unauthorized_ceiling():
    with pytest.raises(RiskAuthorizationError, match="unauthorized"):
        ComposedRiskAuthorizer(_risk(state=RiskState.UNAUTHORIZED))


def test_composed_authorizer_rejects_nonpositive_ceiling():
    with pytest.raises(RiskAuthorizationError, match="authorized_risk"):
        ComposedRiskAuthorizer(_risk(authorized_risk=0.0))


def test_listed_selector_preserves_authorization_identity_and_picks_listed_winner():
    authorization = ComposedRiskAuthorizer(_risk()).authorize(_decision())
    instrument = ListedInstrumentSelector(_chain(), option_type="CE").select(authorization)
    assert instrument.intent_id == authorization.intent_id
    assert instrument.instrument_id == "NIFTY26AUG24500CE"
    assert instrument.selection_id == f"SEL-{authorization.intent_id}"
    assert instrument.selection_version == "listed-v1"


def test_listed_selector_empty_chain_fails_closed():
    authorization = ComposedRiskAuthorizer(_risk()).authorize(_decision())
    with pytest.raises(InstrumentSelectionError, match="empty_listed_universe"):
        ListedInstrumentSelector((), option_type="CE").select(authorization)


def test_f109_and_f114_stay_locked():
    assert FORMULAS["F-109"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED


def _bar(**payload) -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id="TD-BAR-001",
        event_type="bar",
        instrument_id="NIFTY 50",
        event_time="2026-08-17T03:45:00+00:00",
        available_at="2026-08-17T03:45:01+00:00",
        source="truedata",
        source_version="2.6",
        payload=payload,
    )


def test_bar_feature_builder_maps_present_fields_and_does_not_invent_defaults():
    snapshot = BarFeatureBuilder().build(
        _bar(open=24500.0, high=24520.0, low=24490.0, close=24510.0, volume=1500.0, oi=120000.0)
    )
    assert snapshot.snapshot_id == "SNAP-TD-BAR-001"
    assert snapshot.values["close"] == 24510.0
    assert snapshot.values["volume"] == 1500.0
    assert snapshot.values["oi"] == 120000.0
    assert all(status is FeatureStatus.VALID for status in snapshot.statuses.values())


def test_bar_feature_builder_requires_close_and_does_not_invent_it():
    with pytest.raises(ValueError, match="requires close"):
        BarFeatureBuilder().build(_bar(volume=1500.0))


def test_identity_prediction_binds_snapshot_without_inventing_f102():
    snapshot = BarFeatureBuilder().build(_bar(close=24510.0))
    prediction = IdentityPredictionBinder().predict(snapshot)
    assert prediction.snapshot_id == snapshot.snapshot_id
    assert prediction.opportunity_id == "OPP-SNAP-TD-BAR-001"
    assert prediction.prediction_time == snapshot.decision_time
    assert prediction.prediction_value is None
    assert prediction.calibration_reference is None
    assert prediction.provenance["binding"] == "identity-only"


def test_explicit_gross_edge_carries_caller_gross_and_no_f102_score():
    snapshot = BarFeatureBuilder().build(_bar(close=24510.0))
    edge = ExplicitGrossEdge(120.0).evaluate(snapshot)
    assert edge.opportunity_id == "OPP-SNAP-TD-BAR-001"
    assert edge.expected_gross_value == 120.0
    assert edge.score == 0.0
    assert edge.confidence is None
    assert edge.formula_id == "F-004"
    assert FORMULAS["F-102"].status is FormulaStatus.LOCKED
