from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.prediction_contract import (
    OutputType,
    PredictionContractError,
    PredictionProvenance,
    PredictionRecord,
    build_decision_input,
)


def make_prediction(**overrides):
    values = {
        "prediction_id": "pred-1",
        "decision_time": datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc),
        "feature_snapshot_id": "snapshot-1",
        "model_version": "model-1",
        "model_state_version": "state-1",
        "raw_output": 0.7,
        "output_type": OutputType.SCORE,
        "provenance": PredictionProvenance(
            feature_snapshot_id="snapshot-1",
            model_version="model-1",
            model_state_version="state-1",
            calibration_version=None,
        ),
    }
    values.update(overrides)
    return PredictionRecord(**values)


def test_raw_output_is_not_implicitly_probability():
    prediction = make_prediction()
    decision_input = build_decision_input(prediction)
    assert decision_input.prediction_type is OutputType.SCORE
    assert decision_input.prediction_value == 0.7


def test_calibrated_output_requires_calibration_version():
    with pytest.raises(PredictionContractError):
        make_prediction(calibrated_output=0.65)


def test_calibration_changes_decision_input_type_only_when_declared():
    prediction = make_prediction(calibration_version="cal-1", calibrated_output=0.65)
    decision_input = build_decision_input(prediction)
    assert decision_input.prediction_type is OutputType.PROBABILITY
    assert decision_input.prediction_value == 0.65
    assert decision_input.calibration_version == "cal-1"


def test_provenance_must_match_prediction_identity():
    with pytest.raises(PredictionContractError):
        make_prediction(
            provenance=PredictionProvenance(
                feature_snapshot_id="other-snapshot",
                model_version="model-1",
                model_state_version="state-1",
                calibration_version=None,
            )
        )


def test_prediction_requires_timezone_aware_decision_time():
    with pytest.raises(PredictionContractError):
        make_prediction(decision_time=datetime(2026, 8, 11, 10, 0))
