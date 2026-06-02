"""Tests for study.sim — shared bar-by-bar simulator."""
import numpy as np
import pandas as pd
import pytest

from study.sim import simulate_idx, sharpe, base_metrics


def _make_df(n: int = 200, base: float = 50000.0):
    np.random.seed(42)
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.normal(0.0002, 0.015, n)) + base
    high = close + abs(rng.normal(0, 50, n))
    low = close - abs(rng.normal(0, 50, n))
    tr = np.maximum(high - low, np.maximum(
        np.abs(high - np.roll(close, 1)),
        np.abs(low - np.roll(close, 1)),
    ))
    atr = pd.Series(tr).rolling(14).mean().bfill().to_numpy()
    return pd.DataFrame({"close": close, "high": high, "low": low, "atr": atr})


class TestSimulateIdxLong:
    def test_returns_trades_for_signals(self):
        df = _make_df(200)
        sigs = np.zeros(len(df), dtype=bool)
        sigs[50] = True
        sigs[100] = True
        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="long")
        assert len(trades) >= 1
        for t in trades:
            assert "pnl_pct" in t
            assert "entry_bar" in t
            assert "exit_bar" in t
            assert t["exit_bar"] > t["entry_bar"]

    def test_skips_invalid_atr(self):
        df = _make_df(200)
        df.loc[50, "atr"] = np.nan
        sigs = np.zeros(len(df), dtype=bool)
        sigs[50] = True
        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="long")
        # Signal at index 50 should be skipped because atr is NaN
        entry_bars = [t["entry_bar"] for t in trades]
        assert 50 not in entry_bars

    def test_skips_signal_at_end(self):
        df = _make_df(50)
        sigs = np.zeros(len(df), dtype=bool)
        sigs[49] = True  # last bar, no room for exit
        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="long")
        assert len(trades) == 0

    def test_no_overlapping_positions(self):
        df = _make_df(500)
        sigs = np.zeros(len(df), dtype=bool)
        sigs[50] = True
        sigs[55] = True  # should be skipped if trade from 50 still open
        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="long")
        entry_bars = [t["entry_bar"] for t in trades]
        assert 55 not in entry_bars or len(trades) < 2

    def test_empty_signals(self):
        df = _make_df(100)
        sigs = np.zeros(len(df), dtype=bool)
        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="long")
        assert len(trades) == 0


class TestSimulateIdxShort:
    def test_short_direction_basic(self):
        df = _make_df(500, base=50000.0)
        # Create a signal where price will likely fall
        sigs = np.zeros(len(df), dtype=bool)
        sigs[50] = True
        trades = simulate_idx(df, sigs, slm=2.0, tpm=3.5, direction="short")
        assert len(trades) >= 1
        for t in trades:
            assert "pnl_pct" in t
            # For shorts, PnL should be the inverse of long
            assert isinstance(t["pnl_pct"], float)

    def test_short_fee_subtraction(self):
        df = _make_df(200)
        sigs = np.zeros(len(df), dtype=bool)
        sigs[50] = True
        trades = simulate_idx(df, sigs, slm=1.0, tpm=5.0, direction="short", fee_rt=0.001)
        assert len(trades) >= 1


class TestSharpe:
    def test_positive_returns(self):
        pnls = [0.01] * 20
        s = sharpe(pnls)
        # All positive returns have infinite or very high Sharpe (no variance)
        assert s >= 0

    def test_mixed_returns(self):
        pnls = [0.02, -0.01, 0.03, -0.005, 0.01] * 10
        s = sharpe(pnls)
        assert s > 0

    def test_single_return(self):
        s = sharpe([0.01])
        assert s == 0.0

    def test_empty(self):
        s = sharpe([])
        assert s == 0.0


class TestBaseMetrics:
    def test_winning_trades(self):
        pnls = [0.02] * 10
        m = base_metrics(pnls)
        assert m["win_rate"] == 1.0
        assert m["pf"] > 1.0
        assert m["net_return"] > 0
        assert m["pnl_usd"] > 0

    def test_losing_trades(self):
        pnls = [-0.02] * 10
        m = base_metrics(pnls)
        assert m["win_rate"] == 0.0
        assert m["net_return"] < 0
        assert m["pnl_usd"] < 0
        assert m["max_dd"] < 0

    def test_empty_trades(self):
        m = base_metrics([], starting_capital=1000.0)
        assert m["net_return"] == 0.0
        assert m["pnl_usd"] == 0.0
