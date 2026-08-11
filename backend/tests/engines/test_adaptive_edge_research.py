import pytest

from app.engines.adaptive_edge.research_dataset import ResearchRow, validate_dataset
from app.engines.adaptive_edge.walk_forward import build_folds


def row(i: int, day: int) -> ResearchRow:
    stamp = f"2026-01-{day:02d}T10:00:00"
    return ResearchRow(
        row_id=str(i),
        instrument="NIFTY",
        decision_time=stamp,
        feature_values=(float(i),),
        feature_available_at=(f"2026-01-{day:02d}T09:59:00",),
        label_end_time=f"2026-01-{day + 1:02d}T10:00:00",
        label=1,
    )


def test_future_feature_is_rejected():
    bad = ResearchRow("x", "NIFTY", "2026-01-01T10:00:00", (1.0,), ("2026-01-01T10:01:00",), "2026-01-02T10:00:00", 1)
    with pytest.raises(ValueError, match="availability"):
        bad.validate()


def test_dataset_must_be_chronological():
    with pytest.raises(ValueError, match="chronologically"):
        validate_dataset((row(2, 2), row(1, 1)))


def test_walk_forward_has_purge_and_embargo_boundaries():
    rows = tuple(row(i, i + 1) for i in range(12))
    folds = build_folds(rows, train_size=4, validation_size=2, holdout_size=2, purge_rows=1, embargo_rows=1)
    assert len(folds) == 1
    fold = folds[0]
    assert len(fold.train) == 4
    assert len(fold.validation) == 2
    assert len(fold.holdout) == 2
    assert fold.train[-1].decision_time < fold.validation[0].decision_time
    assert fold.validation[-1].decision_time < fold.holdout[0].decision_time
