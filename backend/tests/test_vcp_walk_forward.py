"""
Walk-forward tests for Hybrid VCP-Momentum Scalper.
"""
import pytest
import numpy as np

from app.schemas.market import Candle
from app.engines.hybrid_vcp.walk_forward import (
    run_walk_forward, WalkForwardVCPResult,
    VCPProfileVariant, ALL_VARIANTS, TEST_VARIANTS, VARIANT_PROFILES,
)


class TestVCFWalkForward:
    @staticmethod
    def _synthetic_candles(n=600, base_price=65000.0, seed=42):
        rng = np.random.default_rng(seed)
        ts = int(1_718_000_000_000)
        candles = []
        price = base_price
        for i in range(n):
            price += rng.normal(5, 150)
            o = price - abs(rng.normal(0, 80))
            c = price + abs(rng.normal(0, 80))
            h = max(o, c) + abs(rng.normal(0, 60))
            l = min(o, c) - abs(rng.normal(0, 60))
            candles.append(Candle(
                timestamp_ms=ts + i * 15 * 60_000,
                open=round(o, 2),
                high=round(h, 2),
                low=round(max(l, 100), 2),
                close=round(c, 2),
                volume=round(rng.lognormal(8.0, 0.8), 2),
            ))
        return candles

    def test_walk_forward_runs_without_error(self):
        """run_walk_forward completes on synthetic candles."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80)
        assert isinstance(result, WalkForwardVCPResult)
        assert len(result.windows) >= 1

    def test_windows_have_valid_bounds(self):
        """Each window's train/test boundaries are correct."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80)
        for w in result.windows:
            assert w.train_start < w.train_end
            assert w.test_start < w.test_end
            assert w.train_end == w.test_start
            assert w.train_start >= 0
            assert w.test_end <= len(candles)

    def test_best_variant_in_valid_range(self):
        """Best variant per window has params within swept ranges."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80)
        valid_holds = {12, 16, 20}
        valid_stops = {0.8, 0.9, 1.0}
        valid_flows = {0.30, 0.35, 0.40}
        for w in result.windows:
            assert w.best_variant.hold_bars in valid_holds
            assert w.best_variant.stop_mult in valid_stops
            assert w.best_variant.flow_threshold in valid_flows

    def test_recommended_variant_in_range(self):
        """Recommended variant has params within swept ranges."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80)
        v = result.recommended_variant
        assert v.hold_bars in {12, 16, 20}
        assert v.stop_mult in {0.8, 0.9, 1.0}
        assert v.flow_threshold in {0.30, 0.35, 0.40}

    def test_oos_equity_starts_at_one(self):
        """OOS equity curve starts at 1.0."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80)
        assert len(result.oos_equity_curve) >= 1
        assert abs(result.oos_equity_curve[0] - 1.0) < 1e-6

    def test_aggregate_sharpe_isfinite(self):
        """Aggregate Sharpe is finite (or 0 if no trades)."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80)
        s = result.aggregate_report.sharpe
        assert isinstance(s, float)
        assert -100 <= s <= 100

    def test_windows_0_or_positive_sharpe_when_flag(self):
        """Windows with no_edge=False have non-negative test Sharpe."""
        candles = self._synthetic_candles(n=600)
        result = run_walk_forward(candles, "btc_scalping_15m",
                                  train_bars=200, test_bars=80, step_bars=80,
                                  require_positive_oos=True)
        for w in result.windows:
            if not w.no_edge:
                assert w.test_report.sharpe >= 0.0

    def test_profile_variant_apply_round_trips(self):
        """Variant.apply_to produces a VCPProfile with all fields set."""
        from app.engines.hybrid_vcp.profiles import PROFILES
        base = PROFILES["btc_scalping_15m"]
        variant = VCPProfileVariant(base_key="btc_scalping_15m",
                                    hold_bars=20, stop_mult=0.8,
                                    flow_threshold=0.30)
        p = variant.apply_to(base)
        assert p.hold_bars == 20
        assert p.stop_mult == 0.8
        assert p.flow_threshold == 0.30
        assert p.signal_tf == base.signal_tf
        assert p.regime_tf == base.regime_tf
        assert p.risk_pct == base.risk_pct

    def test_variant_count_reasonable(self):
        """4 base profiles × 3 holds × 3 stops × 3 flows = 108 variants (36 fast test variants)."""
        assert len(ALL_VARIANTS) == 108
        assert len(TEST_VARIANTS) == 12

    def test_all_profiles_have_variants(self):
        """Every base profile key has variants defined."""
        expected_keys = {"btc_scalping_15m", "btc_scalping_30m",
                        "eth_scalping_15m", "eth_scalping_30m"}
        covered = {v.base_key for v in ALL_VARIANTS}
        assert covered == expected_keys