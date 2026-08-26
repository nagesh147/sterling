import pytest

from app.engines.adaptive_edge.parameter_fitting import (
    FittingConfig,
    ParameterFittingError,
    fit_multinomial_logistic,
)


def test_fitter_returns_dimensionally_valid_parameters_and_reduces_loss():
    result = fit_multinomial_logistic(
        features=((-2.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (2.0, 0.0)),
        labels=(0, 0, 1, 1),
        class_names=("DOWN", "UP"),
        config=FittingConfig(learning_rate=0.1, epochs=1000, l2_regularization=0.01),
        model_version="2.1.0-test",
    )
    assert result.final_loss < result.initial_loss
    assert len(result.parameters.coefficients) == 2
    assert len(result.parameters.coefficients[0]) == 2
    assert len(result.parameters.intercepts) == 2
    assert result.epochs_run <= 1000


def test_fitter_is_deterministic():
    kwargs = dict(
        features=((-1.0,), (0.0,), (1.0,)),
        labels=(0, 1, 2),
        class_names=("DOWN", "NEUTRAL", "UP"),
        config=FittingConfig(learning_rate=0.05, epochs=100),
        model_version="2.1.0-test",
    )
    first = fit_multinomial_logistic(**kwargs)
    second = fit_multinomial_logistic(**kwargs)
    assert first == second


def test_fitter_rejects_misaligned_or_invalid_labels():
    config = FittingConfig()
    with pytest.raises(ParameterFittingError):
        fit_multinomial_logistic(
            features=((1.0,),),
            labels=(),
            class_names=("A", "B"),
            config=config,
            model_version="test",
        )
    with pytest.raises(ParameterFittingError):
        fit_multinomial_logistic(
            features=((1.0,),),
            labels=(2,),
            class_names=("A", "B"),
            config=config,
            model_version="test",
        )
