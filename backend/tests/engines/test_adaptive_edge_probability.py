from app.engines.adaptive_edge.master_spec_edge import evaluate_direction
from app.engines.adaptive_edge.probability_engine import ModelParameters


def test_probability_model_is_parameterized_and_reproducible():
    params = ModelParameters(
        version="model-test-1",
        classes=("up", "down", "neutral"),
        coefficients=((1.0, 0.0), (0.0, 1.0), (0.0, 0.0)),
        intercepts=(0.0, 0.0, 0.0),
        regularization=0.1,
    )
    first = evaluate_direction(
        prediction_id="P-1",
        opportunity_id="O-1",
        prediction_time="2026-08-11T09:30:00+05:30",
        feature_snapshot_id="F-1",
        features=(2.0, 0.0),
        parameters=params,
    )
    second = evaluate_direction(
        prediction_id="P-2",
        opportunity_id="O-1",
        prediction_time="2026-08-11T09:30:00+05:30",
        feature_snapshot_id="F-1",
        features=(2.0, 0.0),
        parameters=params,
    )
    assert first.direction == 1
    assert first.prediction.outputs == second.prediction.outputs
    assert abs(sum(first.prediction.outputs.values()) - 1.0) < 1e-12
