from app.engines.adaptive_edge.calibration import CalibrationConfig, calibrate
from app.engines.adaptive_edge.model_selection import CandidateModel, select_model
from app.engines.adaptive_edge.parameter_fitting import FitConfig, fit
from app.engines.adaptive_edge.research_dataset import ResearchRow


def make_rows(n=40):
    rows = []
    for i in range(n):
        minute = i % 60
        hour = 9 + i // 60
        t = f"2026-01-01T{hour:02d}:{minute:02d}:00"
        label = -1 if i % 3 == 0 else (0 if i % 3 == 1 else 1)
        rows.append(ResearchRow(str(i), "NIFTY", t, (float(label), float(i % 5)), (t, t), f"2026-01-01T11:{minute:02d}:00", label))
    return tuple(rows)


def test_calibration_rejects_small_validation_set():
    rows = make_rows(10)
    result = calibrate(rows, params=fit(rows, config=FitConfig(version="fit", epochs=10)).parameters, config=CalibrationConfig(version="cal"))
    assert not result.eligible
    assert "insufficient_validation_rows" in result.reasons


def test_selection_requires_calibration_eligibility():
    rows = make_rows(40)
    params = fit(rows, config=FitConfig(version="fit", epochs=10)).parameters
    calibration = calibrate(rows, params=params, config=CalibrationConfig(version="cal", min_validation_rows=10, max_log_loss=0.01))
    candidate = CandidateModel("m1", "fit", calibration, 100.0, 0.01)
    result = select_model((candidate,))
    assert result.selected_model_id is None or result.frozen
