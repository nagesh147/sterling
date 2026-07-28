from __future__ import annotations

import numpy as np
import pytest

from app.engines.navigator.projected_ranges import (
    _decay_weights,
    _session_groups,
    _weekly_groups,
    _weighted_quantile,
    classify_range_context,
    evaluate_ranges,
)
from app.engines.navigator.quality import validate_candles
from app.engines.navigator.schemas import RangesConfig
from tests.engines.navigator.conftest import multi_session_candles


class TestWeightedQuantile:
    def test_matches_hand_fixture_with_equal_weights(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        weights = np.ones(5)
        # cum weights = [1,2,3,4,5], threshold at q=0.6 -> 3.0 -> searchsorted -> idx2 (value 3)
        assert _weighted_quantile(values, weights, 0.6) == pytest.approx(3.0)

    def test_higher_quantile_returns_higher_or_equal_value(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        weights = np.ones(5)
        assert _weighted_quantile(values, weights, 0.9) >= _weighted_quantile(values, weights, 0.2)

    def test_decay_weights_most_recent_is_heaviest(self):
        w = _decay_weights(5, decay=0.9)
        assert w[-1] == pytest.approx(1.0)
        assert w[0] < w[-1]
        assert list(w) == sorted(w)  # monotonically increasing toward the end


class TestSessionAndWeekGrouping:
    def test_session_groups_partition_by_ist_date(self):
        candles = validate_candles(multi_session_candles(sessions=3, bars_per_session=4, seed=1))
        groups = _session_groups(candles)
        assert groups == [(0, 4), (4, 8), (8, 12)]

    def test_weekly_groups_span_multiple_sessions(self):
        candles = validate_candles(multi_session_candles(sessions=3, bars_per_session=4, seed=1))
        session_groups = _session_groups(candles)
        weekly = _weekly_groups(candles, session_groups)
        # 3 consecutive weekday-adjacent sessions (Mon/Tue/Wed-ish via 18h gaps)
        # should mostly land in the same ISO week -> fewer weekly groups than sessions.
        assert len(weekly) <= len(session_groups)
        assert weekly[0][0] == 0
        assert weekly[-1][1] == session_groups[-1][1]


class TestLeakageFreeFitting:
    def _config(self, **overrides):
        base = dict(
            daily_lookback_sessions=20, daily_min_sessions=5,
            weekly_lookback_periods=10, weekly_min_periods=2,
            min_condition_bucket=100,  # force unconditional (disable bucketing) for determinism
        )
        base.update(overrides)
        return RangesConfig(**base)

    def test_current_session_excluded_from_daily_estimator(self):
        candles = validate_candles(multi_session_candles(sessions=10, bars_per_session=6, seed=3))
        cfg = self._config()
        result = evaluate_ranges(candles, cfg)
        assert result.daily.available is True
        # sample_count must be sessions-1 (today's still-forming session excluded),
        # clipped to the lookback window.
        assert result.daily.sample_count == 9

    def test_current_week_excluded_from_weekly_estimator(self):
        candles = validate_candles(multi_session_candles(sessions=10, bars_per_session=6, seed=3))
        cfg = self._config()
        result = evaluate_ranges(candles, cfg)
        assert result.weekly.available is True
        session_groups = _session_groups(candles)
        weekly_groups = _weekly_groups(candles, session_groups)
        assert result.weekly.sample_count == len(weekly_groups) - 1

    def test_frozen_endpoints_do_not_move_as_the_current_session_unfolds(self):
        candles_list = multi_session_candles(sessions=10, bars_per_session=6, seed=4)
        cfg = self._config()

        # Evaluate using only the first bar of the last (current) session...
        partial = candles_list[: 9 * 6 + 1]
        result_partial = evaluate_ranges(validate_candles(partial), cfg)
        # ...vs. using the full current session's bars.
        full = candles_list
        result_full = evaluate_ranges(validate_candles(full), cfg)

        assert result_partial.daily.upper == pytest.approx(result_full.daily.upper)
        assert result_partial.daily.lower == pytest.approx(result_full.daily.lower)

    def test_insufficient_sessions_returns_unavailable(self):
        candles = validate_candles(multi_session_candles(sessions=3, bars_per_session=4, seed=5))
        cfg = self._config(daily_min_sessions=10)
        result = evaluate_ranges(candles, cfg)
        assert result.daily.available is False
        assert result.daily.unavailable_reason is not None

    def test_quantile_endpoint_matches_manual_computation(self):
        candles = validate_candles(multi_session_candles(sessions=8, bars_per_session=6, seed=9))
        cfg = self._config(decay=1.0, target_coverage=0.5)  # equal weights -> simple weighted quantile
        result = evaluate_ranges(candles, cfg)

        session_groups = _session_groups(candles)
        completed = session_groups[:-1]
        ups, downs = [], []
        for (s, e) in completed:
            po = float(candles.open[s])
            ph = float(candles.high[s:e].max())
            pl = float(candles.low[s:e].min())
            ups.append(max(0.0, (ph - po) / po))
            downs.append(max(0.0, (po - pl) / po))
        weights = np.ones(len(ups))
        expected_upper = float(candles.open[session_groups[-1][0]]) * (1 + _weighted_quantile(np.array(ups), weights, 0.5))
        expected_lower = float(candles.open[session_groups[-1][0]]) * (1 - _weighted_quantile(np.array(downs), weights, 0.5))
        assert result.daily.upper == pytest.approx(expected_upper)
        assert result.daily.lower == pytest.approx(expected_lower)


class TestConditionalBucketLabeling:
    def test_falls_back_to_unconditional_when_bucket_too_small(self):
        candles = validate_candles(multi_session_candles(sessions=10, bars_per_session=6, seed=6))
        cfg = RangesConfig(
            daily_lookback_sessions=20, daily_min_sessions=5, weekly_lookback_periods=10,
            weekly_min_periods=2, condition_on_volatility=True, min_condition_bucket=100,
        )
        result = evaluate_ranges(candles, cfg)
        assert result.daily.available is True
        assert result.daily.conditioned is False  # too few samples per bucket -> unconditional, and labeled as such


class TestRangeContextClassification:
    def _range(self, upper=110.0, lower=90.0):
        from app.engines.navigator.projected_ranges import ProjectedRange
        return ProjectedRange(available=True, period_open=100.0, upper=upper, lower=lower, sample_count=10, target_coverage=0.8)

    def test_inside_balanced(self):
        ctx = classify_range_context(
            range_result=self._range(), period_high=105.0, period_low=95.0, close=100.0,
            edge_tolerance_atr=0.25, atr_value=1.0,
        )
        assert ctx == "INSIDE_BALANCED"

    def test_near_upper(self):
        ctx = classify_range_context(
            range_result=self._range(), period_high=109.9, period_low=95.0, close=109.9,
            edge_tolerance_atr=1.0, atr_value=1.0,
        )
        assert ctx == "NEAR_UPPER"

    def test_break_above(self):
        ctx = classify_range_context(
            range_result=self._range(), period_high=115.0, period_low=95.0, close=112.0,
            edge_tolerance_atr=0.25, atr_value=1.0,
        )
        assert ctx == "BREAK_ABOVE"

    def test_reentered_from_above(self):
        ctx = classify_range_context(
            range_result=self._range(), period_high=115.0, period_low=95.0, close=108.0,
            edge_tolerance_atr=0.25, atr_value=1.0,
        )
        assert ctx == "REENTERED_FROM_ABOVE"

    def test_break_below_and_reentered_mirror(self):
        ctx1 = classify_range_context(
            range_result=self._range(), period_high=105.0, period_low=85.0, close=88.0,
            edge_tolerance_atr=0.25, atr_value=1.0,
        )
        assert ctx1 == "BREAK_BELOW"
        ctx2 = classify_range_context(
            range_result=self._range(), period_high=105.0, period_low=85.0, close=92.0,
            edge_tolerance_atr=0.25, atr_value=1.0,
        )
        assert ctx2 == "REENTERED_FROM_BELOW"

    def test_unavailable_when_range_not_available(self):
        from app.engines.navigator.projected_ranges import ProjectedRange
        unavailable = ProjectedRange(available=False, unavailable_reason="not enough sessions")
        ctx = classify_range_context(
            range_result=unavailable, period_high=105.0, period_low=95.0, close=100.0,
            edge_tolerance_atr=0.25, atr_value=1.0,
        )
        assert ctx == "UNAVAILABLE"
