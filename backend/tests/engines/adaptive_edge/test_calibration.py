import pytest

from app.engines.adaptive_edge.calibration import CalibrationError, CalibrationConfig, fit_temperature, temperature_scale


def test_temperature_scaling_returns_normalized_probabilities():
    probabilities = temperature_scale((2.0, 0.0, -1.0), 1.0)
    assert sum(probabilities) == pytest.approx(1.0)
    assert all(0 <= probability <= 1 for probability in probabilities)


def test_temperature_fitting_is_deterministic_and_uses_validation_data():
    result = fit_temperature(
        validation_logits=((2.0, 0.0), (1.5, 0.0), (-2.0, 0.0), (-1.5, 0.0)),
        validation_labels=(0, 0, 1, 1),
        config=CalibrationConfig(minimum_temperature=0.5, maximum_temperature=2.0, grid_points=31),
    )
    assert 0.5 <= result.temperature <= 2.0
    assert result.validation_log_loss >= 0


def test_temperature_validation_inputs_are_rejected():
    with pytest.raises(CalibrationError):
        temperature_scale((1.0, 2.0), 0)
    with pytest.raises(CalibrationError):
        fit_temperature(validation_logits=((1.0, 2.0),), validation_labels=(), config=CalibrationConfig())
