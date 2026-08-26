import pytest

from app.engines.adaptive_edge.label_maturity import (
    DecisionReference,
    LabelMaturityError,
    OutcomeObservation,
    OutcomeState,
    construct_mature_label,
    training_eligible,
    validate_decision_lineage,
    validate_feature_availability,
)


def decision() -> DecisionReference:
    return DecisionReference(
        decision_id="decision-1",
        decision_time_ms=1_000,
        strategy_version="2.1.0",
        feature_snapshot_id="features-1",
        prediction_version="prediction-1",
        economic_assessment_id="economic-1",
        eligibility_id="eligibility-1",
        risk_authorization_id="risk-1",
        instrument_id="NIFTY",
    )


def test_feature_must_be_available_by_decision_time():
    validate_feature_availability(999, 1_000)

    with pytest.raises(LabelMaturityError):
        validate_feature_availability(1_001, 1_000)


def test_outcome_must_reference_decision_and_cannot_precede_it():
    d = decision()
    validate_decision_lineage(d, OutcomeObservation("decision-1", 1_001, 1_100, OutcomeState.MATURE))

    with pytest.raises(LabelMaturityError):
        validate_decision_lineage(d, OutcomeObservation("other", 1_001, 1_100, OutcomeState.MATURE))

    with pytest.raises(LabelMaturityError):
        validate_decision_lineage(d, OutcomeObservation("decision-1", 999, 1_100, OutcomeState.MATURE))


def test_immature_outcome_cannot_construct_label():
    d = decision()
    outcome = OutcomeObservation("decision-1", 1_001, None)

    with pytest.raises(LabelMaturityError):
        construct_mature_label(d, outcome, "label-v1", 2_000)


def test_label_cannot_be_constructed_before_maturity():
    d = decision()
    outcome = OutcomeObservation("decision-1", 1_001, 2_000, OutcomeState.MATURE)

    with pytest.raises(LabelMaturityError):
        construct_mature_label(d, outcome, "label-v1", 1_999)


def test_mature_label_is_eligible_only_at_or_after_training_cutoff_boundary():
    d = decision()
    outcome = OutcomeObservation("decision-1", 1_001, 2_000, OutcomeState.MATURE)
    label = construct_mature_label(d, outcome, "label-v1", 2_000)

    assert training_eligible(label, 1_999) is False
    assert training_eligible(label, 2_000) is True
