from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f104_horizon import HORIZON_BUCKETS, HorizonDistribution, distribution_from_scores


def test_f104_preserves_six_source_horizon_buckets() -> None:
    assert HORIZON_BUCKETS == (
        "MICRO_SCALP",
        "SHORT_SCALP",
        "SCALP",
        "EXTENDED_SCALP",
        "INTRADAY",
        "LONG_TAIL",
    )


def test_f104_distribution_is_normalized_and_deterministic() -> None:
    scores = (2.0, 1.0, 0.0, -1.0, -2.0, -3.0)
    first = distribution_from_scores(scores)
    second = distribution_from_scores(scores)
    assert first == second
    assert sum(first.probabilities) == pytest.approx(1.0)
    assert first.management_class == "MICRO_SCALP"


def test_f104_rejects_invalid_distribution() -> None:
    with pytest.raises(ValueError):
        HorizonDistribution((0.5, 0.5, 0.0, 0.0, 0.0))

    with pytest.raises(ValueError):
        HorizonDistribution((1.0, 0.0, 0.0, 0.0, 0.0, 0.1))


def test_f104_does_not_invent_tail_midpoint() -> None:
    distribution = HorizonDistribution((0.0, 0.0, 0.0, 0.0, 0.0, 1.0))
    assert distribution.dominant_bucket == "LONG_TAIL"
    assert distribution.management_class == "INTRADAY"
