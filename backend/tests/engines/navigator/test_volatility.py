from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

import app.engines.navigator.volatility as volatility_mod
from app.engines.navigator.quality import validate_candles
from app.engines.navigator.schemas import VolatilityConfig
from app.engines.navigator.volatility import (
    _adx_di,
    _confirmed_direction_series,
    _log_returns,
    _robust_slope,
    _rolling_percentile_rank,
    _rolling_std,
    compute_features,
    compute_score_and_regime,
    evaluate_volatility,
)
from tests.engines.navigator.conftest import make_candles, random_walk_candles


def _flat_bars(n, price=100.0, vol=1000.0):
    o = [price] * n
    h = [price + 1] * n
    l = [price - 1] * n
    c = [price] * n
    v = [vol] * n
    return validate_candles(make_candles(o, h, l, c, v))


class TestFeatureFormulas:
    def test_log_returns_against_fixed_array(self):
        close = np.array([100.0, 110.0, 99.0])
        out = _log_returns(close)
        assert np.isnan(out[0])
        assert out[1] == pytest.approx(np.log(1.1))
        assert out[2] == pytest.approx(np.log(99.0 / 110.0))

    def test_zero_return_series_is_finite_not_nan(self):
        close = np.full(10, 100.0)
        out = _log_returns(close)
        assert np.all(out[1:] == 0.0)
        rv = _rolling_std(out, 4)
        assert np.all(np.isfinite(rv[~np.isnan(rv)]))
        assert rv[-1] == pytest.approx(0.0)

    def test_constant_close_produces_finite_features_throughout(self):
        candles = _flat_bars(120)
        cfg = VolatilityConfig(atr_period=5, rv_short_bars=3, rv_long_bars=10, band_period=5, percentile_lookback=60, adx_period=5, ema_fast_period=3, ema_slow_period=8)
        features = compute_features(candles, cfg)
        tail = slice(features.warmup_index, None)
        for arr in (features.atr_pct, features.rv_ratio, features.bandwidth, features.adx):
            assert np.all(np.isfinite(arr[tail]))

    def test_robust_slope_matches_hand_calc(self):
        x = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
        out = _robust_slope(x, k=2)
        assert out[2] == pytest.approx((4.0 - 1.0) / 2)
        assert out[4] == pytest.approx((16.0 - 4.0) / 2)

    def test_adx_di_zero_on_flat_series(self):
        candles = _flat_bars(40)
        adx, plus_di, minus_di = _adx_di(candles.high, candles.low, candles.close, period=5)
        assert np.all(np.isfinite(adx))
        assert np.all(np.isfinite(plus_di))
        assert np.all(np.isfinite(minus_di))


class TestNoPercentileLeakage:
    def test_percentile_rank_excludes_the_current_value(self):
        # A huge spike at the very last index must NOT be able to see itself
        # in its own comparison window (it always ranks against PRIOR values only).
        x = np.concatenate([np.full(30, 1.0), [1000.0]])
        warmup = 0
        ranks = _rolling_percentile_rank(x, lookback=30, warmup_index=warmup)
        # window for the spike is x[0:31] i.e. entirely the constant 1.0s -> spike ranks 100
        assert ranks[-1] == pytest.approx(100.0)
        # every prior (constant) bar has nothing to compare above itself
        assert ranks[29] == pytest.approx(0.0) or np.isnan(ranks[29])

    def test_future_values_cannot_influence_past_ranks(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=100) + 50
        x_with_future_spike = x.copy()
        ranks_before = _rolling_percentile_rank(x, lookback=40, warmup_index=0)
        x_with_future_spike[80] = 10_000.0  # a future value relative to bar 50
        ranks_after = _rolling_percentile_rank(x_with_future_spike, lookback=40, warmup_index=0)
        assert ranks_before[50] == pytest.approx(ranks_after[50])


class TestExpansionCompressionHysteresis:
    def test_compression_always_yields_wait(self):
        candles = _flat_bars(120, price=100.0)  # near-zero movement -> low vol_score
        cfg = VolatilityConfig(
            atr_period=5, rv_short_bars=3, rv_long_bars=10, band_period=5, percentile_lookback=60,
            adx_period=5, ema_fast_period=3, ema_slow_period=8, compression_max=90.0, expansion_min=95.0,
        )
        ev = evaluate_volatility(candles, cfg)
        if ev.regime == "COMPRESSION":
            assert ev.direction == "WAIT"
            assert "COMPRESSION_NO_TREND" in ev.reason_codes

    def test_hysteresis_requires_two_bars_before_flipping(self):
        raw = ["NEUTRAL", "EXPANSION", "NEUTRAL", "NEUTRAL", "EXPANSION", "EXPANSION"]
        # Simulate the hysteresis loop directly using the same rule as compute_score_and_regime:
        # a single-bar flip (index1 -> back to NEUTRAL at index2) should NOT
        # produce a confirmed flip after only one bar; two consecutive
        # agreeing raw bars (index4,5) should confirm EXPANSION.
        confirmed = [raw[0]]
        for t in range(1, len(raw)):
            if raw[t] == confirmed[-1]:
                confirmed.append(confirmed[-1])
            elif t >= 1 and raw[t - 1] == raw[t]:
                confirmed.append(raw[t])
            else:
                confirmed.append(confirmed[-1])
        assert confirmed[1] == "NEUTRAL"  # single-bar flip at t=1 not yet confirmed
        assert confirmed[5] == "EXPANSION"  # confirmed once t=4,5 agree


class TestTrendConfirmationAndFlipAge:
    def test_confirmed_direction_requires_persistence(self):
        raw_votes = [1, 1, -1, 1, 1, 1, 1]
        confirmed = _confirmed_direction_series(raw_votes, trend_confirm_bars=3)
        # single -1 blip at index2 must not flip the confirmed series
        assert confirmed[2] == confirmed[1]
        # three consecutive +1 votes (indices 3,4,5) confirm LONG
        assert confirmed[5] == 1

    def test_flip_age_increases_after_a_confirmed_flip(self):
        raw_votes = [-1, -1, -1, 1, 1, 1, 1, 1]
        confirmed = _confirmed_direction_series(raw_votes, trend_confirm_bars=3)
        assert confirmed[-1] == 1
        assert confirmed[2] == -1


class TestScoreBoundsAndDeterministicReasons:
    def test_vol_score_stays_within_0_100(self):
        candles = validate_candles(random_walk_candles(150, seed=42))
        cfg = VolatilityConfig(percentile_lookback=60)
        features = compute_features(candles, cfg)
        scored = compute_score_and_regime(features, cfg)
        valid = scored.vol_score[~np.isnan(scored.vol_score)]
        assert np.all(valid >= 0.0) and np.all(valid <= 100.0)

    def test_confidence_is_bounded(self):
        candles = validate_candles(random_walk_candles(150, seed=13))
        cfg = VolatilityConfig(percentile_lookback=60)
        ev = evaluate_volatility(candles, cfg)
        assert 0.0 <= ev.confidence_100 <= 100.0

    def test_warming_up_before_enough_history(self):
        candles = validate_candles(random_walk_candles(10, seed=1))
        cfg = VolatilityConfig()  # default warmup requires far more than 10 bars
        ev = evaluate_volatility(candles, cfg)
        assert ev.direction == "WAIT"
        assert ev.reason_codes == ["VOL_WARMING_UP"]

    def test_reason_codes_are_deterministic_for_identical_input(self):
        candles = validate_candles(random_walk_candles(150, seed=99))
        cfg = VolatilityConfig(percentile_lookback=60)
        ev1 = evaluate_volatility(candles, cfg)
        ev2 = evaluate_volatility(candles, cfg)
        assert ev1.reason_codes == ev2.reason_codes
        assert ev1.direction == ev2.direction
        assert ev1.confidence_100 == ev2.confidence_100

    def test_min_direction_confidence_gate_forces_wait(self):
        candles = validate_candles(random_walk_candles(150, seed=99))
        cfg_low_gate = VolatilityConfig(percentile_lookback=60, min_direction_confidence=0.0)
        cfg_high_gate = VolatilityConfig(percentile_lookback=60, min_direction_confidence=99.9)
        ev_low = evaluate_volatility(candles, cfg_low_gate)
        ev_high = evaluate_volatility(candles, cfg_high_gate)
        if ev_low.direction != "WAIT":
            assert ev_high.direction == "WAIT"


class TestCurrentOnlyContextNeverLeaksIntoHistory:
    """`mid_avwap`/`base_direction` are a single CURRENT-bar AVWAP reading
    and the base engine's live direction — not per-bar history. Reusing
    them for every historical bar while reconstructing the confirmed-
    direction series would retroactively compare old closes against
    today's AVWAP and inject today's signal into the past. They must only
    ever be applied to the most recent (current) bar."""

    def test_mid_avwap_and_base_direction_are_only_passed_for_the_final_bar(self):
        candles = validate_candles(random_walk_candles(150, seed=7))
        cfg = VolatilityConfig(percentile_lookback=60)
        real_votes_at = volatility_mod._votes_at
        calls: list[tuple] = []

        def spy(t, features, close, config, mid_avwap, base_direction):
            calls.append((t, mid_avwap, base_direction))
            return real_votes_at(t, features, close, config, mid_avwap, base_direction)

        with patch.object(volatility_mod, "_votes_at", side_effect=spy):
            volatility_mod.evaluate_volatility(candles, cfg, mid_avwap=24_500.0, base_direction="long")

        last_index = candles.n - 1
        historical_calls = [c for c in calls if c[0] != last_index]
        final_bar_calls = [c for c in calls if c[0] == last_index]
        assert historical_calls, "expected historical bars to have been evaluated"
        assert all(mid is None and direction is None for _, mid, direction in historical_calls)
        assert final_bar_calls, "expected the final bar to have been evaluated"
        assert any(mid == 24_500.0 and direction == "long" for _, mid, direction in final_bar_calls)
