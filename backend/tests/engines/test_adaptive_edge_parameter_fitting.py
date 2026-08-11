from app.engines.adaptive_edge.parameter_fitting import FitConfig, fit
from app.engines.adaptive_edge.research_dataset import ResearchRow


def row(i: int, values: tuple[float, float], label: int) -> ResearchRow:
    t = f"2026-01-01T09:{i:02d}:00"
    return ResearchRow(
        row_id=str(i),
        instrument="NIFTY",
        decision_time=t,
        feature_values=values,
        feature_available_at=(t, t),
        label_end_time=f"2026-01-01T10:{i:02d}:00",
        label=label,
    )


def test_fit_produces_three_class_model_and_validation_metrics():
    train = tuple(
        [row(i, (float(i), float(i % 2)), -1) for i in range(3)]
        + [row(i, (float(i), float(i % 2)), 1) for i in range(3, 6)]
        + [row(6, (0.0, 0.5), 0)]
    )
    validation = (row(7, (6.0, 0.0), 1), row(8, (0.0, 1.0), -1), row(9, (0.0, 0.5), 0))
    result = fit(
        train,
        config=FitConfig(version="wf-1", learning_rate=0.05, epochs=100, l2=0.001),
        validation=validation,
    )
    assert result.parameters.version == "wf-1"
    assert result.parameters.classes == ("DOWN", "FLAT", "UP")
    assert len(result.parameters.coefficients) == 3
    assert result.validation_loss is not None
    assert result.validation_accuracy is not None
    assert 0.0 <= result.validation_accuracy <= 1.0


def test_validation_rows_do_not_change_fitted_parameters():
    train = tuple(
        [row(i, (float(i), float(i % 2)), -1) for i in range(3)]
        + [row(i, (float(i), float(i % 2)), 1) for i in range(3, 6)]
        + [row(6, (0.0, 0.5), 0)]
    )
    config = FitConfig(version="wf-1", learning_rate=0.05, epochs=100, l2=0.001)
    normal = fit(train, config=config, validation=(row(7, (6.0, 0.0), 1),))
    contradictory = fit(train, config=config, validation=(row(7, (6.0, 0.0), -1),))

    assert normal.parameters == contradictory.parameters
    assert normal.validation_loss != contradictory.validation_loss


def test_fit_rejects_empty_training_set():
    try:
        fit((), config=FitConfig(version="wf-1"))
    except ValueError as exc:
        assert "training set" in str(exc)
    else:
        raise AssertionError("empty training set must be rejected")


def test_fit_rejects_inconsistent_feature_dimensions():
    train = (row(1, (-1.0, 0.0), -1), row(2, (1.0, 0.0), 1))
    invalid = ResearchRow(
        row_id="3",
        instrument="NIFTY",
        decision_time="2026-01-01T09:03:00",
        feature_values=(0.0, 1.0, 2.0),
        feature_available_at=(
            "2026-01-01T09:03:00",
            "2026-01-01T09:03:00",
            "2026-01-01T09:03:00",
        ),
        label_end_time="2026-01-01T10:03:00",
        label=0,
    )
    try:
        fit(train + (invalid,), config=FitConfig(version="wf-1"))
    except ValueError as exc:
        assert "feature dimensions" in str(exc)
    else:
        raise AssertionError("inconsistent feature dimensions must be rejected")
