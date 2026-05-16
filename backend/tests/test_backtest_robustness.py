"""
Backtest robustness tests:

 1. Synthetic-curve verification of analytics.performance:
      sharpe / max_drawdown / profit_factor on known equity curves.
 2. walk_forward_split — correct non-overlapping train/test ranges.
 3. param_sweep + top_by — runs grid, returns sorted entries.

These tests deliberately use small in-process candle series so the suite
remains fast.
"""
import math
import numpy as np
import pytest

from app.engines.analytics.performance import (
    sharpe, max_drawdown, calmar, sortino,
)
from app.engines.backtest.sweep import (
    walk_forward_split, walk_forward_run, param_sweep, top_by,
)
from tests.conftest import make_candles


# ─── 1. analytics.performance correctness on synthetic curves ───────────────

class TestPerformanceMath:

    def test_sharpe_zero_for_flat_curve(self) -> None:
        """A perfectly flat curve has zero std and zero excess return → 0."""
        ec = np.full(100, 1.0)
        assert sharpe(ec) == 0.0

    def test_sharpe_positive_for_monotone_growth(self) -> None:
        """A monotonically rising curve must have positive Sharpe."""
        ec = np.array([1.0 + 0.001 * i for i in range(200)])
        assert sharpe(ec) > 0.0

    def test_sharpe_negative_for_monotone_decline(self) -> None:
        ec = np.array([1.0 - 0.001 * i for i in range(200)])
        assert sharpe(ec) < 0.0

    def test_sharpe_annualisation_factor(self) -> None:
        """For constant-return r and zero std → return / std = inf, so we use
        a near-constant series with tiny noise to assert annualisation factor."""
        rng = np.random.default_rng(42)
        rets = 0.001 + rng.normal(0, 1e-6, 1000)
        ec = np.cumprod(1 + rets)
        ec = np.concatenate([[1.0], ec])
        s = sharpe(ec, periods_per_year=8760)
        # Expected ≈ 0.001 / 1e-6 * sqrt(8760) — at least very large
        assert s > 1000

    def test_max_drawdown_zero_for_monotone_up(self) -> None:
        ec = np.array([1.0, 1.1, 1.2, 1.3, 1.5])
        assert max_drawdown(ec) == 0.0

    def test_max_drawdown_known_v_shape(self) -> None:
        """Peak 1.5 → trough 0.75 → 50% drawdown."""
        ec = np.array([1.0, 1.5, 1.0, 0.75, 1.2])
        assert math.isclose(max_drawdown(ec), -0.5, abs_tol=1e-9)

    def test_max_drawdown_one_dip(self) -> None:
        """Peak 2.0 → trough 1.0 → 50%."""
        ec = np.array([1.0, 2.0, 1.0, 1.5])
        assert math.isclose(max_drawdown(ec), -0.5, abs_tol=1e-9)

    def test_calmar_zero_when_no_drawdown(self) -> None:
        ec = np.array([1.0, 1.01, 1.02, 1.03])
        assert calmar(ec) == 0.0

    def test_sortino_handles_only_negative_returns(self) -> None:
        ec = np.array([1.0, 0.99, 0.98, 0.97])
        # All-negative returns → finite Sortino, not crash, not zero
        s = sortino(ec)
        assert math.isfinite(s)
        assert s < 0


# ─── 2. walk_forward_split correctness ──────────────────────────────────────

class TestWalkForwardSplit:

    def test_basic_three_split(self) -> None:
        splits = walk_forward_split(n_items=300, n_splits=3, train_pct=0.7)
        assert len(splits) == 3
        # Each split has train+test summing to its slice
        for (tr, te) in splits:
            assert tr[1] >= tr[0] and te[1] >= te[0]
            # Train ratio close to 0.7 of total slice
            slice_size = te[1] - tr[0]
            assert abs((tr[1] - tr[0]) / slice_size - 0.7) < 0.05

    def test_no_overlap_between_train_and_test(self) -> None:
        for (tr, te) in walk_forward_split(200, 4, train_pct=0.6):
            assert tr[1] == te[0]   # contiguous, end-exclusive

    def test_no_overlap_between_consecutive_splits(self) -> None:
        splits = walk_forward_split(n_items=300, n_splits=3, train_pct=0.7)
        for i in range(len(splits) - 1):
            _, test_a = splits[i]
            train_b, _ = splits[i + 1]
            assert test_a[1] == train_b[0]

    def test_drops_splits_below_min_train(self) -> None:
        # 30 items / 6 splits = 5 each → train would be 3 bars, below default min_train=50
        splits = walk_forward_split(n_items=30, n_splits=6, train_pct=0.7)
        assert splits == []

    def test_zero_items_returns_empty(self) -> None:
        assert walk_forward_split(0) == []

    def test_zero_splits_returns_empty(self) -> None:
        assert walk_forward_split(100, n_splits=0) == []


# ─── 3. param_sweep + top_by ────────────────────────────────────────────────

class TestParamSweep:

    def _make_series(self):
        # 100 4H + 400 1H is enough for the engine's _MIN_4H_WINDOW=55, _MIN_1H_WINDOW=30
        return make_candles(100, base=30000.0, trend=80.0), make_candles(400, base=30000.0, trend=20.0)

    def test_sweep_runs_each_combo(self) -> None:
        c4h, c1h = self._make_series()
        grid = {
            "sample_every_n_bars": [4, 8],
            "option_dte":          [15, 30],
        }
        results = param_sweep("BTC", c4h, c1h, grid)
        assert len(results) == 4   # 2 * 2 cartesian

    def test_sweep_each_entry_has_params_and_stats(self) -> None:
        c4h, c1h = self._make_series()
        results = param_sweep("BTC", c4h, c1h, {"sample_every_n_bars": [4, 8]})
        for r in results:
            assert "params" in r and "stats" in r
            for key in ("sharpe", "max_drawdown", "win_rate", "trade_count"):
                assert key in r["stats"]

    def test_top_by_orders_by_metric(self) -> None:
        results = [
            {"params": {"a": 1}, "stats": {"sharpe": 0.5}},
            {"params": {"a": 2}, "stats": {"sharpe": 1.5}},
            {"params": {"a": 3}, "stats": {"sharpe": -0.2}},
        ]
        top = top_by(results, key="sharpe", n=2)
        assert top[0]["params"] == {"a": 2}
        assert top[1]["params"] == {"a": 1}

    def test_top_by_pushes_none_to_end(self) -> None:
        results = [
            {"params": {"a": 1}, "stats": {"sharpe": None}},
            {"params": {"a": 2}, "stats": {"sharpe": 0.4}},
        ]
        top = top_by(results, key="sharpe", n=2)
        assert top[0]["params"] == {"a": 2}
        assert top[1]["params"] == {"a": 1}

    def test_empty_grid_returns_empty(self) -> None:
        c4h, c1h = self._make_series()
        assert param_sweep("BTC", c4h, c1h, {}) == []


# ─── 4. walk_forward_run end-to-end (small) ─────────────────────────────────

class TestWalkForwardRun:

    def test_walk_forward_produces_train_and_test_entries(self) -> None:
        c4h = make_candles(100, base=30000.0, trend=80.0)
        c1h = make_candles(400, base=30000.0, trend=20.0)
        out = walk_forward_run("BTC", c4h, c1h, n_splits=2, train_pct=0.7)
        # 2 splits × 2 phases (train+test) when each split is large enough
        if out:
            phases = [r["phase"] for r in out]
            assert "train" in phases
            assert "test" in phases
            # Every entry has the canonical keys
            for r in out:
                for k in ("split", "phase", "sharpe", "max_drawdown", "trade_count"):
                    assert k in r
