from datetime import datetime, timedelta, timezone

import pytest

from app.engines.adaptive_edge.normalization import (
    NormalizationContext,
    Observation,
    conditional_percentile,
)

UTC = timezone.utc
BASE = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)


def ts(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def context(*, regime: str | None = None) -> NormalizationContext:
    return NormalizationContext(
        instrument="NIFTY",
        time_of_day="OPEN",
        volatility_state="NORMAL",
        expiry_state="CURRENT",
        market_regime=regime,
    )


def test_empirical_cdf_uses_only_causally_available_matching_context():
    current = context(regime="TREND")
    other = context(regime="RANGE")
    result = conditional_percentile(
        20.0,
        decision_time=ts(10),
        context=current,
        history=(
            Observation(10.0, ts(1), current),
            Observation(20.0, ts(2), current),
            Observation(30.0, ts(11), current),
            Observation(999.0, ts(2), other),
        ),
    )
    assert result.percentile == pytest.approx(1.0)
    assert result.sample_size == 2


def test_percentile_is_right_continuous_empirical_cdf():
    current = context()
    result = conditional_percentile(
        20.0,
        decision_time=ts(3),
        context=current,
        history=(
            Observation(10.0, ts(1), current),
            Observation(20.0, ts(2), current),
            Observation(20.0, ts(3), current),
            Observation(30.0, ts(3), current),
        ),
    )
    assert result.percentile == pytest.approx(3 / 4)


def test_equal_decision_time_is_eligible_under_section_19_data_boundary():
    current = context()
    result = conditional_percentile(
        10.0,
        decision_time=ts(2),
        context=current,
        history=(Observation(10.0, ts(2), current),),
    )
    assert result.sample_size == 1
    assert result.percentile == 1.0


def test_no_causal_matching_history_is_rejected_without_inventing_a_value():
    current = context()
    with pytest.raises(ValueError, match="insufficient causal normalization history"):
        conditional_percentile(
            10.0,
            decision_time=ts(2),
            context=current,
            history=(Observation(10.0, ts(3), current),),
        )
