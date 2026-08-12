from datetime import datetime, timezone

import pytest

from app.engines.adaptive_edge.horizon_distribution import HorizonError, HorizonObservation, build_horizon_distribution

UTC = timezone.utc


def test_horizon_distribution_is_empirical_and_quantile_queryable():
    observations = (
        HorizonObservation(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 1, tzinfo=UTC), -0.02),
        HorizonObservation(datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 1, 2, 1, tzinfo=UTC), 0.01),
        HorizonObservation(datetime(2026, 1, 3, tzinfo=UTC), datetime(2026, 1, 3, 1, tzinfo=UTC), 0.03),
    )
    result = build_horizon_distribution(observations, horizon_bars=15)
    assert result.sample_size == 3
    assert result.mean_return == pytest.approx(0.006666666666666667)
    assert result.quantile(0.5) == pytest.approx(0.01)


def test_horizon_rejects_non_future_observations():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(HorizonError, match="after decision time"):
        build_horizon_distribution((HorizonObservation(now, now, 0.0),), horizon_bars=15)
