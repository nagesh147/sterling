import pytest

from app.engines.adaptive_edge.operational_controls import (
    HealthState,
    OperationalControlDecision,
    OperationalControlError,
    OperationalObservation,
    SafetyAction,
    apply_operational_control,
)


def observation():
    return OperationalObservation("obs-1", "market-data", 1000, HealthState.DEGRADED, "evidence-1")


def decision(**overrides):
    values = dict(
        decision_id="decision-1",
        observation_id="obs-1",
        action=SafetyAction.BLOCK_NEW,
        policy_id="policy-1",
        policy_version="1",
        rationale="new entries blocked",
    )
    values.update(overrides)
    return OperationalControlDecision(**values)


def test_operational_control_preserves_observation_identity():
    assert apply_operational_control(observation(), decision()).observation_id == "obs-1"


def test_operational_control_rejects_mismatched_observation():
    with pytest.raises(OperationalControlError):
        apply_operational_control(observation(), decision(observation_id="obs-2"))


def test_operational_observation_requires_evidence():
    with pytest.raises(OperationalControlError):
        OperationalObservation("obs-1", "market-data", 1000, HealthState.FAILED, "")


def test_operational_observation_rejects_negative_timestamp():
    with pytest.raises(OperationalControlError):
        OperationalObservation("obs-1", "market-data", -1, HealthState.FAILED, "evidence-1")
