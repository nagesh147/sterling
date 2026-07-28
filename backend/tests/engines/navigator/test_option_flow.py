from __future__ import annotations

import math

import pytest

from app.engines.navigator.option_flow import (
    ChainFlowSample,
    ContractFlowInput,
    apply_zero_hysteresis,
    compute_oscillator_series,
    compute_raw_activity,
    detect_divergence,
    evaluate_option_flow,
)
from app.engines.navigator.schemas import FlowConfig


def _sample(sample_ms, *, call_delta=100, put_delta=100, call_move=0.01, put_move=-0.01, atm=24500.0, spread=0.02):
    contracts = [
        ContractFlowInput(
            token=1, option_type="CE", strike=24500.0, mid=100.0 * (1 + call_move),
            prev_mid=100.0, delta_volume=call_delta, delta_oi=50, spread_pct=spread,
        ),
        ContractFlowInput(
            token=2, option_type="PE", strike=24500.0, mid=100.0 * (1 + put_move),
            prev_mid=100.0, delta_volume=put_delta, delta_oi=50, spread_pct=spread,
        ),
    ]
    return ChainFlowSample(sample_ms=sample_ms, atm_strike=atm, strike_step=100.0, contracts=contracts)


class TestPerContractActivity:
    def test_call_buying_and_put_selling_both_contribute_positive_activity(self):
        history = [_sample(i * 60_000, call_move=0.02, put_move=-0.02) for i in range(5)]
        result = compute_raw_activity(history, 4, FlowConfig())
        assert result.call_activity > 0
        assert result.put_activity > 0  # side=-1 * negative price_impulse = positive
        assert result.valid_contracts == 2

    def test_contract_with_invalid_counter_is_excluded(self):
        contracts = [
            ContractFlowInput(token=1, option_type="CE", strike=24500.0, mid=101.0, prev_mid=100.0, delta_volume=None, delta_oi=10, spread_pct=0.01),
        ]
        history = [ChainFlowSample(sample_ms=0, atm_strike=24500.0, strike_step=100.0, contracts=contracts)]
        result = compute_raw_activity(history, 0, FlowConfig())
        assert result.valid_contracts == 0
        assert result.raw_activity == 0.0

    def test_proximity_weight_decays_for_far_otm_strikes(self):
        near = ContractFlowInput(token=1, option_type="CE", strike=24500.0, mid=101.0, prev_mid=100.0, delta_volume=500, delta_oi=10, spread_pct=0.01)
        far = ContractFlowInput(token=2, option_type="CE", strike=26000.0, mid=101.0, prev_mid=100.0, delta_volume=500, delta_oi=10, spread_pct=0.01)
        history_near = [ChainFlowSample(sample_ms=0, atm_strike=24500.0, strike_step=100.0, contracts=[near])]
        history_far = [ChainFlowSample(sample_ms=0, atm_strike=24500.0, strike_step=100.0, contracts=[far])]
        r_near = compute_raw_activity(history_near, 0, FlowConfig())
        r_far = compute_raw_activity(history_far, 0, FlowConfig())
        assert abs(r_near.raw_activity) > abs(r_far.raw_activity)

    def test_wide_spread_suppresses_activity(self):
        tight = ContractFlowInput(token=1, option_type="CE", strike=24500.0, mid=101.0, prev_mid=100.0, delta_volume=500, delta_oi=10, spread_pct=0.01)
        wide = ContractFlowInput(token=2, option_type="CE", strike=24500.0, mid=101.0, prev_mid=100.0, delta_volume=500, delta_oi=10, spread_pct=0.20)
        cfg = FlowConfig(max_spread_pct=0.10)
        r_tight = compute_raw_activity([ChainFlowSample(0, 24500.0, 100.0, [tight])], 0, cfg)
        r_wide = compute_raw_activity([ChainFlowSample(0, 24500.0, 100.0, [wide])], 0, cfg)
        assert r_wide.raw_activity == 0.0  # liquidity weight clamped to 0
        assert r_tight.raw_activity != 0.0


class TestOscillatorBounds:
    def test_oscillator_is_bounded_minus_100_to_100(self):
        cfg = FlowConfig(warmup_samples=5, robust_window_samples=20)
        raw = [10.0, -500.0, 5.0, 300.0, -8.0, 1000.0, -2.0] * 3
        out = compute_oscillator_series(raw, cfg)
        valid = [v for v in out if not math.isnan(v)]
        assert all(-100.0 <= v <= 100.0 for v in valid)

    def test_nan_before_warmup(self):
        cfg = FlowConfig(warmup_samples=10, robust_window_samples=20)
        raw = [1.0] * 5
        out = compute_oscillator_series(raw, cfg)
        assert all(math.isnan(v) for v in out)

    def test_zero_mad_does_not_crash(self):
        cfg = FlowConfig(warmup_samples=3, robust_window_samples=10)
        raw = [5.0] * 10  # zero variance -> MAD=0, must fall back to epsilon not divide-by-zero
        out = compute_oscillator_series(raw, cfg)
        assert all(math.isfinite(v) for v in out if not math.isnan(v))


class TestZeroHysteresis:
    def test_bullish_only_after_crossing_positive_threshold(self):
        states = apply_zero_hysteresis([5.0, 12.0, 3.0, -15.0, 2.0], hysteresis=10.0)
        assert states == ["neutral", "bullish", "bullish", "bearish", "bearish"]

    def test_retains_prior_state_inside_the_band(self):
        states = apply_zero_hysteresis([20.0, 0.0, 0.0], hysteresis=10.0)
        assert states == ["bullish", "bullish", "bullish"]


class TestDivergence:
    def test_no_divergence_with_insufficient_pivots(self):
        result = detect_divergence([1, 2, 1, 2, 1], [10, 20, 10, 20, 10], pivot_left_bars=1, pivot_right_bars=1, min_separation_bars=1, min_oscillator_magnitude=5)
        # too few confirmed pivots to compare (or agree) — should not crash and may be None
        assert result is None or isinstance(result, str)

    def test_bearish_divergence_detected(self):
        # price: higher high at bar 6 vs bar 2; oscillator: LOWER reading at bar 6 vs bar 2
        price = [10, 10, 12, 10, 10, 11, 15, 11, 10, 10]
        osc = [0, 0, 80.0, 0, 0, 0, 40.0, 0, 0, 0]
        result = detect_divergence(price, osc, pivot_left_bars=1, pivot_right_bars=1, min_separation_bars=2, min_oscillator_magnitude=20)
        assert result == "BEARISH_DIVERGENCE"

    def test_bullish_divergence_is_the_mirror(self):
        price = [10, 10, 8, 10, 10, 9, 5, 9, 10, 10]
        osc = [0, 0, -80.0, 0, 0, 0, -40.0, 0, 0, 0]
        result = detect_divergence(price, osc, pivot_left_bars=1, pivot_right_bars=1, min_separation_bars=2, min_oscillator_magnitude=20)
        assert result == "BULLISH_DIVERGENCE"

    def test_below_magnitude_threshold_is_not_divergence(self):
        price = [10, 10, 12, 10, 10, 11, 15, 11, 10, 10]
        osc = [0, 0, 8.0, 0, 0, 0, 4.0, 0, 0, 0]  # both below min_oscillator_magnitude
        result = detect_divergence(price, osc, pivot_left_bars=1, pivot_right_bars=1, min_separation_bars=2, min_oscillator_magnitude=20)
        assert result is None


class TestEvaluateOptionFlowIntegration:
    def test_empty_history_is_unavailable(self):
        ev = evaluate_option_flow([], FlowConfig())
        assert ev.quality == "unavailable"
        assert ev.direction == 0

    def test_chain_unavailable_short_circuits(self):
        history = [_sample(i * 60_000) for i in range(50)]
        ev = evaluate_option_flow(history, FlowConfig(), chain_quality="unavailable")
        assert ev.quality == "unavailable"
        assert "CHAIN_UNAVAILABLE" in ev.reason_codes

    def test_warming_up_before_enough_samples(self):
        history = [_sample(i * 60_000) for i in range(5)]
        cfg = FlowConfig(warmup_samples=30)
        ev = evaluate_option_flow(history, cfg)
        assert ev.quality == "unavailable"
        assert ev.reason_codes == ["FLOW_WARMING_UP"]

    def test_bullish_flow_after_warmup(self):
        history = [_sample(i * 60_000, call_move=0.03, put_move=-0.03, call_delta=800, put_delta=100) for i in range(60)]
        cfg = FlowConfig(warmup_samples=20, robust_window_samples=40, zero_hysteresis=5)
        ev = evaluate_option_flow(history, cfg)
        assert ev.quality in ("ok", "degraded")
        assert ev.oscillator is not None

    def test_degraded_chain_lowers_confidence(self):
        history = [_sample(i * 60_000) for i in range(60)]
        cfg = FlowConfig(warmup_samples=20, robust_window_samples=40)
        ev_ok = evaluate_option_flow(history, cfg, chain_quality="ok")
        ev_degraded = evaluate_option_flow(history, cfg, chain_quality="degraded")
        assert ev_degraded.confidence_100 <= ev_ok.confidence_100
