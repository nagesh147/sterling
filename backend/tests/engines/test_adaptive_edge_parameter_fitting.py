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
    train = tuple(row(i, (float(i), float(i % 2)), -1 if i < 2 else 1) for i in range(6))
    validation = (row(6, (6.0, 0.0), 1), row(7, (0.0, 1.0), -1))
    result = fit(train, config=FitConfig(version="wf-1", epochs=50), validation=validation)
    assert result.parameters.version == "wf-1"
    assert result.parameters.classes == ("DOWN", "FLAT", "UP")
    assert len(result.parameters.coefficients) == 3
    assert result.validation_loss is not None
    assert result.validation_accuracy is not None


def test_fit_rejects_empty_training_set():
    try:
        fit((), config=FitConfig(version="wf-1"))
    except ValueError as exc:
        assert "training set" in str(exc)
    else:
        raise AssertionError("empty training set must be rejected")
