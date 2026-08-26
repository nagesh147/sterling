from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f101_normalization import F101Observation, fit_f101


BASE = "2026-08-17T09:30:00+05:30"
AFTER = "2026-08-17T09:31:00+05:30"


def test_f101_uses_empirical_cdf_and_is_deterministic() -> None:
    model = fit_f101(
        [
            F101Observation(BASE, 1.0, "TREND_UP"),
            F101Observation(BASE, 2.0, "TREND_UP"),
            F101Observation(BASE, 3.0, "TREND_UP"),
        ],
        training_end=BASE,
    )

    assert model.transform(F101Observation(AFTER, 2.0, "TREND_UP")) == pytest.approx(2 / 3)
    assert model.transform(F101Observation(AFTER, 3.0, "TREND_UP")) == pytest.approx(1.0)


def test_f101_rejects_training_lookahead() -> None:
    with pytest.raises(ValueError, match="after training_end"):
        fit_f101(
            [F101Observation(AFTER, 2.0, "TREND_UP")],
            training_end=BASE,
        )


def test_f101_rejects_transform_before_frozen_training_boundary() -> None:
    model = fit_f101(
        [F101Observation(BASE, 1.0)],
        training_end=BASE,
    )

    with pytest.raises(ValueError, match="precedes normalization training boundary"):
        model.transform(F101Observation("2026-08-17T09:29:00+05:30", 1.0))


def test_f101_does_not_silently_cross_contexts() -> None:
    model = fit_f101(
        [F101Observation(BASE, 1.0, "TREND_UP")],
        training_end=BASE,
    )

    with pytest.raises(ValueError, match="no normalization distribution"):
        model.transform(F101Observation(AFTER, 1.0, "TREND_DOWN"))


def test_f101_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        fit_f101([F101Observation(BASE, float("nan"))], training_end=BASE)
