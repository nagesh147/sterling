from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f102_prediction import build_f102_model
from app.engines.adaptive_edge.feature_engine import (
    FeatureInput,
    FeatureProvenance,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)


def snapshot(*, value: float = 1.0, status: FeatureStatus = FeatureStatus.VALID):
    return build_feature_snapshot(
        snapshot_id="snap-1",
        strategy_version="1.0",
        feature_set_version="1.0",
        observation_cutoff_time="2026-08-17T09:30:00+05:30",
        decision_time="2026-08-17T09:30:00+05:30",
        instrument_context=InstrumentContext("NIFTY"),
        inputs=[
            FeatureInput(
                name="f1",
                value=value,
                available_at="2026-08-17T09:30:00+05:30",
                status=status,
                provenance=FeatureProvenance(source_event_ids=("e1",)),
            )
        ],
    )


def model():
    return build_f102_model(
        ["f1"],
        {
            "UP": [2.0],
            "DOWN": [-2.0],
            "NEUTRAL": [0.0],
        },
        {"UP": 0.0, "DOWN": 0.0, "NEUTRAL": 0.0},
    )


def test_f102_produces_normalized_probabilities() -> None:
    prediction = model().predict(snapshot(value=1.0))

    assert sum(prediction.probabilities.values()) == pytest.approx(1.0)
    assert prediction.probabilities["UP"] > prediction.probabilities["DOWN"]
    assert prediction.preferred_direction == "UP"
    assert prediction.directional_edge > 0


def test_f102_is_deterministic_for_frozen_coefficients() -> None:
    first = model().predict(snapshot(value=0.25))
    second = model().predict(snapshot(value=0.25))

    assert first == second


def test_f102_rejects_missing_or_invalid_feature_status() -> None:
    with pytest.raises(ValueError, match="invalid F-102 feature status"):
        model().predict(snapshot(status=FeatureStatus.MISSING))


def test_f102_rejects_non_finite_feature_value() -> None:
    with pytest.raises(ValueError, match="invalid F-102 feature value"):
        model().predict(snapshot(value=float("nan")))


def test_f102_rejects_feature_order_mismatch() -> None:
    bad_model = build_f102_model(
        ["missing"],
        {"UP": [1.0], "DOWN": [-1.0], "NEUTRAL": [0.0]},
        {"UP": 0.0, "DOWN": 0.0, "NEUTRAL": 0.0},
    )
    with pytest.raises(ValueError, match="missing F-102 feature"):
        bad_model.predict(snapshot())
