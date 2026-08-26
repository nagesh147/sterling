from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.prediction_contract import (
    DecisionInput,
    OutputType,
    PredictionContractError,
    PredictionProvenance,
    PredictionRecord,
    build_decision_input,
)

UTC = timezone.utc


def prediction(**overrides):
    values = {
        "prediction_id": "p-1",
        "decision_time": datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
        "feature_snapshot_id": "snap-1",
        "model_version": "model-1",
        "model_state_version": "state-1",
        "raw_output": 0.7,
        "output_type": OutputType.SCORE,
    }
    values.update(overrides)
    return PredictionRecord(**values)


def test_raw_score_is_not_implicitly_a_probability():
    result = prediction()
    assert result.output_type is OutputType.SCORE
    assert result.raw_output == 0.7


def test_probability_output_requires_probability_domain():
    with pytest.raises(PredictionContractError, match="within \[0, 1\]"):
        prediction(output_type=OutputType.PROBABILITY, raw_output=1.2)


def test_prediction_provenance_must_match_identity():
    with pytest.raises(PredictionContractError, match="model version mismatch"):
        prediction(provenance=PredictionProvenance("snap-1", "model-2", "state-1", None))


def test_calibrated_output_requires_version_and_probability_domain():
    with pytest.raises(PredictionContractError, match="calibration_version"):
        prediction(calibrated_output=0.8)


def test_decision_input_consumes_calibrated_output_without_deciding():
    result = build_decision_input(prediction(calibration_version="cal-1", calibrated_output=0.81), economic_context_reference="econ-1")
    assert result.prediction_type is OutputType.PROBABILITY
    assert result.prediction_value == 0.81
    assert result.calibration_version == "cal-1"
    assert result.economic_context_reference == "econ-1"


def test_decision_input_is_not_trade_eligibility():
    result = DecisionInput("p-1", OutputType.SCORE, 0.7, None, "snap-1", None, "model-1", datetime(2026, 8, 12, 10, 0, tzinfo=UTC))
    assert result.prediction_id == "p-1"
