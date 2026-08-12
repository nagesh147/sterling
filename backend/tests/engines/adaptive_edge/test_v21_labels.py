from datetime import datetime, timedelta, timezone

import pytest

from app.engines.adaptive_edge.v21_labels import (
    LabelStatus,
    MarketObservation,
    TargetSpec,
    build_label,
    preregistered_specs,
)

UTC = timezone.utc


def obs(minutes: int, price: float, *, available_delay: int = 0) -> MarketObservation:
    t = datetime(2026, 8, 12, 9, 15, tzinfo=UTC) + timedelta(minutes=minutes)
    return MarketObservation(t, t + timedelta(minutes=available_delay), price)


def test_up_label_uses_future_only_for_outcome() -> None:
    rows = [obs(0, 100), obs(1, 100), obs(2, 100), obs(3, 100), obs(4, 100), obs(5, 101)]
    label = build_label(rows, decision_index=0, spec=TargetSpec(5, 0.005, "test"))
    assert label.status is LabelStatus.MATURE
    assert label.label == "UP"
    assert label.return_value == pytest.approx(0.01)
    assert label.label_maturity_time == rows[5].availability_time


def test_neutral_band_is_explicit() -> None:
    rows = [obs(0, 100), obs(1, 100), obs(2, 100), obs(3, 100), obs(4, 100), obs(5, 100.1)]
    label = build_label(rows, decision_index=0, spec=TargetSpec(5, 0.005, "test"))
    assert label.label == "NEUTRAL"


def test_down_label_is_symmetric() -> None:
    rows = [obs(0, 100), obs(1, 100), obs(2, 100), obs(3, 100), obs(4, 100), obs(5, 99)]
    label = build_label(rows, decision_index=0, spec=TargetSpec(5, 0.005, "test"))
    assert label.label == "DOWN"


def test_terminal_observation_missing_is_pending_not_negative() -> None:
    rows = [obs(0, 100), obs(1, 100), obs(2, 100)]
    label = build_label(rows, decision_index=0, spec=TargetSpec(5, 0.0, "test"))
    assert label.status is LabelStatus.PENDING
    assert label.label is None


def test_terminal_availability_may_be_after_market_timestamp() -> None:
    rows = [obs(0, 100), obs(1, 100), obs(2, 100), obs(3, 100), obs(4, 100), obs(5, 101, available_delay=2)]
    label = build_label(rows, decision_index=0, spec=TargetSpec(5, 0.005, "test"))
    assert label.status is LabelStatus.MATURE
    assert label.label_maturity_time == rows[5].availability_time


def test_decision_observation_must_be_available_at_decision() -> None:
    rows = [obs(0, 100, available_delay=1), obs(1, 101)]
    label = build_label(rows, decision_index=0, spec=TargetSpec(1, 0.0, "test"))
    assert label.status is LabelStatus.INVALID
    assert label.label is None


def test_preregistered_grid_is_exactly_16_candidates() -> None:
    specs = preregistered_specs()
    assert len(specs) == 16
    assert {(s.horizon_bars, s.neutral_threshold) for s in specs} == {
        (h, t)
        for h in (5, 10, 15, 30)
        for t in (0.0, 0.001, 0.0025, 0.005)
    }
