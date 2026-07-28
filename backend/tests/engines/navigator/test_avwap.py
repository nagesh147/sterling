from __future__ import annotations

import numpy as np
import pytest

from app.engines.navigator import avwap
from app.engines.navigator.avwap import (
    AvwapStructure,
    _bearish_structure,
    _bullish_structure,
    _confirmed_pivots,
    _continuation_long_raw,
    _continuation_short_raw,
    _grade_pullback,
    _piecewise_avwap,
    _pullback_long_raw,
    _pullback_short_raw,
    compute_structure,
    evaluate_avwap,
    propose_stop_target,
)
from app.engines.navigator.quality import validate_candles
from app.engines.navigator.schemas import AvwapConfig
from tests.engines.navigator.conftest import make_candles, multi_session_candles, random_walk_candles


# ─────────────────────────────────────────────────────────────────────────
# Confirmed pivots + hand-calculated AVWAP (spec §7.1, §20.1)
# ─────────────────────────────────────────────────────────────────────────

def _pivot_fixture_high():
    return np.array([10, 10, 12, 10, 10, 11, 13, 11, 10, 10], dtype=float)


class TestConfirmedPivots:
    def test_isolated_highs_are_confirmed_with_correct_visibility(self):
        pivots = _confirmed_pivots(_pivot_fixture_high(), left=1, right=1, kind="high")
        assert [(p.bar_index, p.visible_from_index) for p in pivots] == [(2, 3), (6, 7)]

    def test_tie_breaking_keeps_most_recent_of_a_plateau(self):
        # Two-bar plateau at indices 2 and 3 (both = 12), flat elsewhere.
        values = np.array([8, 8, 12, 12, 8, 8], dtype=float)
        pivots = _confirmed_pivots(values, left=1, right=1, kind="high")
        # only bar 3 (the later of the tie) should be confirmed, not bar 2
        assert [p.bar_index for p in pivots] == [3]
        assert pivots[0].visible_from_index == 4

    def test_pivot_low_is_the_mirror_condition(self):
        values = np.array([10, 10, 8, 10, 10, 9, 7, 9, 10, 10], dtype=float)
        pivots = _confirmed_pivots(values, left=1, right=1, kind="low")
        assert [(p.bar_index, p.visible_from_index) for p in pivots] == [(2, 3), (6, 7)]


class TestHandCalculatedAvwap:
    """Volume held constant (=100) and low/close/open fixed relative to
    high, so AVWAP reduces to a plain mean of typical price over the
    anchor window — hand-verifiable."""

    def _typical_and_volume(self):
        high = _pivot_fixture_high()
        # typical = (h + (h-1) + (h-0.5)) / 3 = h - 0.5
        typical = high - 0.5
        volume = np.full_like(high, 100.0)
        return typical, volume

    def test_avwap_includes_the_anchor_bar_even_before_it_is_visible(self):
        typical, volume = self._typical_and_volume()
        anchor_idx = np.array([-1, -1, -1, 2, 2, 2, 2, 6, 6, 6])
        out = _piecewise_avwap(typical, volume, anchor_idx)
        expected = {3: 10.5, 4: 10.1666667, 5: 10.25, 6: 10.7, 7: 11.5, 8: 10.8333333, 9: 10.5}
        for t, val in expected.items():
            assert out[t] == pytest.approx(val, abs=1e-4), f"t={t}"
        assert np.isnan(out[0]) and np.isnan(out[1]) and np.isnan(out[2])

    def test_anchor_switch_uses_the_new_anchor_immediately(self):
        typical, volume = self._typical_and_volume()
        anchor_idx = np.array([-1, -1, -1, 2, 2, 2, 2, 6, 6, 6])
        out = _piecewise_avwap(typical, volume, anchor_idx)
        # t=6 (still anchor 2) vs t=7 (anchor switches to 6) must differ sharply
        assert out[6] != pytest.approx(out[7])

    def test_zero_volume_denominator_is_unavailable_not_close(self):
        typical, _ = self._typical_and_volume()
        volume = np.zeros_like(typical)
        anchor_idx = np.array([-1, -1, -1, 2, 2, 2, 2, 6, 6, 6])
        out = _piecewise_avwap(typical, volume, anchor_idx)
        assert np.isnan(out[3]) and np.isnan(out[9])


class TestNoBackfill:
    def test_high_anchor_idx_is_unset_before_visibility_and_set_after(self):
        n = 10
        high = _pivot_fixture_high() + 100.0  # shift-invariant; keeps low >= 0 below
        low = high - 20.0  # keep low pivots out of the way entirely
        close = high - 0.5
        open_ = high - 0.5
        volume = np.full(n, 100.0)
        candles = validate_candles(make_candles(open_, high, low, close, volume))
        cfg = AvwapConfig(pivot_left_bars=1, pivot_right_bars=1)
        structure = compute_structure(candles, cfg)
        assert list(structure.high_anchor_idx[:3]) == [-1, -1, -1]
        assert list(structure.high_anchor_idx[3:7]) == [2, 2, 2, 2]
        assert list(structure.high_anchor_idx[7:]) == [6, 6, 6]


# ─────────────────────────────────────────────────────────────────────────
# Session VWAP (spec §7.1, §20.1)
# ─────────────────────────────────────────────────────────────────────────

class TestSessionVwap:
    def test_resets_each_ist_session(self):
        candles = validate_candles(multi_session_candles(sessions=3, bars_per_session=4, seed=5))
        structure = compute_structure(candles, AvwapConfig())
        # Manually recompute session VWAP per 4-bar session and compare.
        typical = candles.typical_price()
        volume = candles.volume
        for session in range(3):
            s, e = session * 4, session * 4 + 4
            for i in range(s, e):
                expected = float(np.sum(typical[s:i + 1] * volume[s:i + 1]) / np.sum(volume[s:i + 1]))
                assert structure.session_vwap[i] == pytest.approx(expected, rel=1e-9)

    def test_weekend_gap_still_starts_a_clean_new_session(self):
        # multi_session_candles always inserts an 18h gap; a real weekend gap
        # (much larger) must behave identically — just a new IST date.
        candles = validate_candles(
            multi_session_candles(sessions=2, bars_per_session=3, seed=6, overnight_gap_ms=3 * 24 * 3_600_000)
        )
        structure = compute_structure(candles, AvwapConfig())
        # first bar of session 2 (index 3) must reset — its session VWAP must
        # equal that single bar's typical price, not include session 1 at all.
        typical = candles.typical_price()
        assert structure.session_vwap[3] == pytest.approx(typical[3])


# ─────────────────────────────────────────────────────────────────────────
# Signal family conditions — hand-built structures for full determinism
# ─────────────────────────────────────────────────────────────────────────

def _base_candles(n=6):
    o = [100.0] * n
    h = [101.0] * n
    l = [99.0] * n
    c = [100.5] * n
    v = [1000.0] * n
    return validate_candles(make_candles(o, h, l, c, v))


def _flat_structure(n, *, mid, upper, lower, atr, mid_slope, upper_slope=0.05, lower_slope=0.05, rel_vol=1.5, warming=False):
    ones = np.ones(n)
    return AvwapStructure(
        upper=upper * ones, mid=mid * ones, lower=lower * ones, session_vwap=mid * ones,
        mid_slope=mid_slope * ones, upper_slope=upper_slope * ones, lower_slope=lower_slope * ones,
        warming_up=np.full(n, warming), high_anchor_idx=np.zeros(n, dtype=int), low_anchor_idx=np.zeros(n, dtype=int),
        atr=atr * ones, relative_volume=rel_vol * ones, high_pivots=[], low_pivots=[],
    )


class TestBullishBearishStructureSymmetry:
    def test_bullish_requires_close_above_mid_and_positive_slope(self):
        candles = _base_candles(3)  # close=100.5
        cfg = AvwapConfig()
        structure = _flat_structure(3, mid=100.0, upper=101.0, lower=99.0, atr=1.0, mid_slope=0.05)
        assert _bullish_structure(2, structure, candles, cfg) is True

    def test_bearish_is_the_exact_mirror(self):
        # close=100.5 must be BELOW mid for bearish — flip mid to 101
        candles = _base_candles(3)
        cfg = AvwapConfig()
        structure = _flat_structure(3, mid=101.0, upper=102.0, lower=100.0, atr=1.0, mid_slope=-0.05, upper_slope=-0.05, lower_slope=-0.05)
        assert _bearish_structure(2, structure, candles, cfg) is True

    def test_warming_up_blocks_both(self):
        candles = _base_candles(3)
        cfg = AvwapConfig()
        structure = _flat_structure(3, mid=100.0, upper=101.0, lower=99.0, atr=1.0, mid_slope=0.05, warming=True)
        assert _bullish_structure(2, structure, candles, cfg) is False
        assert _bearish_structure(2, structure, candles, cfg) is False


class TestPullbackLongShortSymmetry:
    def test_pullback_long_fires_on_clean_rejection_at_lower(self):
        n = 3
        o = [100.0, 100.0, 99.6]
        h = [101.0, 101.0, 100.2]
        l = [99.0, 99.0, 98.55]  # touches lower(=98.5) within 0.2 ATR tolerance
        c = [100.5, 100.5, 100.0]  # closes back above mid(99.5), body >= open (bullish)
        candles = validate_candles(make_candles(o, h, l, c, [1000.0] * n))
        cfg = AvwapConfig(touch_tolerance_atr=0.20, max_extension_atr=5.0)
        structure = _flat_structure(n, mid=99.5, upper=100.5, lower=98.5, atr=1.0, mid_slope=0.05)
        assert _pullback_long_raw(2, structure, candles, cfg) is True

    def test_pullback_short_is_the_exact_mirror(self):
        n = 3
        o = [100.0, 100.0, 100.4]
        h = [101.0, 101.0, 101.45]  # touches upper(=101.5) within tolerance
        l = [99.0, 99.0, 99.8]
        c = [99.5, 99.5, 100.0]  # closes back below mid(100.5)
        candles = validate_candles(make_candles(o, h, l, c, [1000.0] * n))
        cfg = AvwapConfig(touch_tolerance_atr=0.20, max_extension_atr=5.0)
        structure = _flat_structure(n, mid=100.5, upper=101.5, lower=99.5, atr=1.0, mid_slope=-0.05, upper_slope=-0.05, lower_slope=-0.05)
        assert _pullback_short_raw(2, structure, candles, cfg) is True

    def test_max_extension_rejects_an_overstretched_close(self):
        n = 3
        o = [100.0, 100.0, 99.6]
        h = [101.0, 101.0, 105.5]
        l = [99.0, 99.0, 98.55]
        c = [100.5, 100.5, 105.0]  # closes WAY above mid — too extended
        candles = validate_candles(make_candles(o, h, l, c, [1000.0] * n))
        cfg = AvwapConfig(touch_tolerance_atr=0.20, max_extension_atr=0.5)
        structure = _flat_structure(n, mid=99.5, upper=100.5, lower=98.5, atr=1.0, mid_slope=0.05)
        assert _pullback_long_raw(2, structure, candles, cfg) is False


class TestContinuationLongShortSymmetry:
    def test_continuation_long_fires_on_a_clean_breakout(self):
        n = 3
        # prior close (t=1) <= upper(100.5)+buffer; current close (t=2) breaks out
        o = [100.0, 100.3, 100.6]
        c = [100.3, 100.4, 101.2]
        h = [100.5, 100.6, 101.3]
        l = [99.9, 100.0, 100.5]
        candles = validate_candles(make_candles(o, h, l, c, [2000.0] * n))
        cfg = AvwapConfig(breakout_buffer_atr=0.05, min_body_atr=0.3, min_relative_volume=1.0, max_extension_atr=5.0)
        structure = _flat_structure(n, mid=99.5, upper=100.5, lower=98.5, atr=1.0, mid_slope=0.05, rel_vol=1.5)
        assert _continuation_long_raw(2, structure, candles, cfg) is True

    def test_continuation_short_is_the_exact_mirror(self):
        n = 3
        o = [100.0, 99.7, 99.4]
        c = [99.7, 99.6, 98.8]
        h = [100.1, 100.0, 99.5]
        l = [99.5, 99.4, 98.7]
        candles = validate_candles(make_candles(o, h, l, c, [2000.0] * n))
        cfg = AvwapConfig(breakout_buffer_atr=0.05, min_body_atr=0.3, min_relative_volume=1.0, max_extension_atr=5.0)
        structure = _flat_structure(n, mid=100.5, upper=101.5, lower=99.5, atr=1.0, mid_slope=-0.05, upper_slope=-0.05, lower_slope=-0.05, rel_vol=1.5)
        assert _continuation_short_raw(2, structure, candles, cfg) is True

    def test_insufficient_relative_volume_blocks_continuation(self):
        n = 3
        o = [100.0, 100.3, 100.6]
        c = [100.3, 100.4, 101.2]
        h = [100.5, 100.6, 101.3]
        l = [99.9, 100.0, 100.5]
        candles = validate_candles(make_candles(o, h, l, c, [2000.0] * n))
        cfg = AvwapConfig(breakout_buffer_atr=0.05, min_body_atr=0.3, min_relative_volume=3.0, max_extension_atr=5.0)
        structure = _flat_structure(n, mid=99.5, upper=100.5, lower=98.5, atr=1.0, mid_slope=0.05, rel_vol=1.5)
        assert _continuation_long_raw(2, structure, candles, cfg) is False


class TestCooldown:
    def test_cooldown_suppresses_the_next_signal_within_window(self):
        # cooldown_bars=2 requires strictly MORE than 2 bars since the last
        # fire before a new one is allowed through.
        mask = np.array([True, True, True, True, True])
        out = avwap._apply_cooldown(mask, cooldown_bars=2)
        assert list(out) == [True, False, False, True, False]

    def test_zero_cooldown_lets_every_raw_signal_through(self):
        mask = np.array([True, True, True])
        out = avwap._apply_cooldown(mask, cooldown_bars=0)
        assert list(out) == [True, True, True]


class TestGradeComponents:
    def test_component_scores_sum_to_total(self):
        n = 3
        o = [100.0, 100.0, 99.6]
        h = [101.0, 101.0, 100.2]
        l = [99.0, 99.0, 98.55]
        c = [100.5, 100.5, 100.0]
        candles = validate_candles(make_candles(o, h, l, c, [1000.0] * n))
        cfg = AvwapConfig(touch_tolerance_atr=0.20, max_extension_atr=5.0)
        structure = _flat_structure(n, mid=99.5, upper=100.5, lower=98.5, atr=1.0, mid_slope=0.05)
        result = _grade_pullback(2, structure, candles, cfg, "long", range_supports=True)
        assert result.score == pytest.approx(sum(result.components.values()), abs=1e-6)
        assert set(result.components) == {"structure", "trigger", "participation", "candle_quality", "extension", "range_context"}

    def test_grade_boundaries_are_respected(self):
        cfg = AvwapConfig(grade_a_plus_min=85, grade_a_min=75, grade_b_min=65)
        assert avwap._grade_label(90, cfg) == "A+"
        assert avwap._grade_label(85, cfg) == "A+"
        assert avwap._grade_label(84.9, cfg) == "A"
        assert avwap._grade_label(75, cfg) == "A"
        assert avwap._grade_label(65, cfg) == "B"
        assert avwap._grade_label(64.9, cfg) == "none"


# ─────────────────────────────────────────────────────────────────────────
# Stop / target proposal (spec §7.4)
# ─────────────────────────────────────────────────────────────────────────

class TestStopTargetProposal:
    def test_accepts_a_valid_long_proposal(self):
        cfg = AvwapConfig(stop_buffer_atr=0.1, max_stop_distance_atr=3.0, target_r=2.0)
        result = propose_stop_target(
            direction="long", entry_reference=100.0, trigger_bar_low=99.0, trigger_bar_high=100.5,
            upper=101.0, lower=98.5, atr=1.0, tick_size=0.05, config=cfg,
        )
        assert result.accepted is True
        assert result.stop < 100.0
        assert result.target > 100.0
        assert result.target - 100.0 == pytest.approx(2.0 * result.risk_points)

    def test_rejects_stop_on_wrong_side_of_entry(self):
        cfg = AvwapConfig()
        # lower/trigger_bar_low both ABOVE entry_reference -> stop ends up above entry for a long
        result = propose_stop_target(
            direction="long", entry_reference=90.0, trigger_bar_low=99.0, trigger_bar_high=100.5,
            upper=101.0, lower=98.5, atr=1.0, tick_size=0.05, config=cfg,
        )
        assert result.accepted is False
        assert "wrong side" in result.reject_reason

    def test_rejects_risk_at_or_below_tick_size(self):
        cfg = AvwapConfig(stop_buffer_atr=0.0)
        result = propose_stop_target(
            direction="long", entry_reference=100.0, trigger_bar_low=100.0, trigger_bar_high=100.5,
            upper=101.0, lower=100.0, atr=1.0, tick_size=1.0, config=cfg,
        )
        assert result.accepted is False

    def test_rejects_when_risk_exceeds_max_stop_distance_atr(self):
        cfg = AvwapConfig(stop_buffer_atr=0.1, max_stop_distance_atr=0.5)
        result = propose_stop_target(
            direction="long", entry_reference=100.0, trigger_bar_low=90.0, trigger_bar_high=100.5,
            upper=101.0, lower=85.0, atr=1.0, tick_size=0.05, config=cfg,
        )
        assert result.accepted is False

    def test_short_is_the_exact_mirror(self):
        cfg = AvwapConfig(stop_buffer_atr=0.1, max_stop_distance_atr=3.0, target_r=2.0)
        result = propose_stop_target(
            direction="short", entry_reference=100.0, trigger_bar_low=99.5, trigger_bar_high=101.0,
            upper=101.5, lower=99.0, atr=1.0, tick_size=0.05, config=cfg,
        )
        assert result.accepted is True
        assert result.stop > 100.0
        assert result.target < 100.0

    def test_range_edge_inside_target_rejects(self):
        cfg = AvwapConfig(stop_buffer_atr=0.1, max_stop_distance_atr=3.0, target_r=2.0)
        result = propose_stop_target(
            direction="long", entry_reference=100.0, trigger_bar_low=99.0, trigger_bar_high=100.5,
            upper=101.0, lower=98.5, atr=1.0, tick_size=0.05, config=cfg,
            nearest_range_edge=100.5,  # closer than the R-multiple target
        )
        assert result.accepted is False
        assert "range edge" in result.reject_reason


# ─────────────────────────────────────────────────────────────────────────
# Integration smoke tests
# ─────────────────────────────────────────────────────────────────────────

class TestEvaluateAvwapIntegration:
    def test_runs_end_to_end_on_a_random_walk(self):
        candles = validate_candles(random_walk_candles(250, seed=11))
        structure, ev = evaluate_avwap(candles, AvwapConfig())
        assert structure.n if hasattr(structure, "n") else True
        assert ev.direction in (-1, 0, 1)

    def test_warming_up_before_both_anchors_exist(self):
        candles = validate_candles(random_walk_candles(5, seed=1))
        structure, ev = evaluate_avwap(candles, AvwapConfig(pivot_left_bars=3, pivot_right_bars=3))
        assert ev.warming_up is True
        assert ev.direction == 0
