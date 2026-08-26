from datetime import datetime, timedelta, timezone

import pytest

from app.engines.adaptive_edge.normalization import NormalizationContext, Observation, conditional_percentile


def test_future_observation_is_excluded():
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    context = NormalizationContext("NIFTY", "09:15")
    history = (
        Observation(1.0, t0 - timedelta(minutes=2), context),
        Observation(2.0, t0 - timedelta(minutes=1), context),
        Observation(100.0, t0 + timedelta(minutes=1), context),
    )
    result = conditional_percentile(2.0, decision_time=t0, context=context, history=history)
    assert result.sample_size == 2
    assert result.percentile == 1.0


def test_different_context_is_excluded():
    t0 = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)
    context = NormalizationContext("NIFTY", "09:15", volatility_state="high")
    other = NormalizationContext("NIFTY", "09:15", volatility_state="low")
    history = (Observation(1.0, t0 - timedelta(minutes=1), other),)
    with pytest.raises(ValueError):
        conditional_percentile(1.0, decision_time=t0, context=context, history=history)
