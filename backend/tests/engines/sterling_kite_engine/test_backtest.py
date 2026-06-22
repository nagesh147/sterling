"""Tests for the Kite options backtest engine (workstream H)."""
import numpy as np
import pytest

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.services.kite_engine import backtest as bt


def _ohlc(closes):
    c = np.asarray(closes, float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + 1.0
    l = np.minimum(o, c) - 1.0
    ts = [i * 3_600_000 for i in range(len(c))]
    return ts, list(o), list(h), list(l), list(c)


class TestCostModel:
    def test_round_trip_charges_positive_and_stt_on_sell(self):
        costs = bt.OptionCosts()
        ch = costs.round_trip(entry_premium=100, exit_premium=120, qty=50)
        assert ch > 0
        # a higher sell premium → more STT → strictly higher charges than a flat exit
        ch_flat = bt.OptionCosts().round_trip(100, 100, 50)
        assert ch > ch_flat

    def test_slippage_scales_with_override(self):
        lo = bt.OptionCosts(slippage_pct=0.0).round_trip(100, 110, 50)
        hi = bt.OptionCosts(slippage_pct=0.05).round_trip(100, 110, 50)
        assert hi > lo


class TestReplayPremiumSeries:
    def test_trends_produce_winning_trade(self):
        # premium dips then rises → a genuine up-transition fires; the long rides
        # the rise to a profitable exit. (A monotonic rise has no FRESH transition
        # after warmup, so a dip is needed to arm the entry.)
        path = list(np.linspace(120, 60, 50)) + list(np.linspace(60, 300, 90))
        ts, o, h, l, c = _ohlc(path)
        cfg = SterlingKiteEngineConfig(trail_target="mid")
        run = bt.replay_premium_series(
            timestamps_ms=ts, premium_open=o, premium_high=h, premium_low=l,
            premium_close=c, cfg=cfg, trail_target="mid", qty=50,
            costs=bt.OptionCosts(), starting_capital=100_000)
        assert run.stats.trades >= 1
        assert run.stats.net_pnl > 0
        assert len(run.equity_curve) == run.stats.trades + 1

    def test_too_few_bars_no_trades(self):
        ts, o, h, l, c = _ohlc([100, 101, 102])
        cfg = SterlingKiteEngineConfig()
        run = bt.replay_premium_series(
            timestamps_ms=ts, premium_open=o, premium_high=h, premium_low=l,
            premium_close=c, cfg=cfg, trail_target="mid", qty=50,
            costs=bt.OptionCosts(), starting_capital=100_000)
        assert run.stats.trades == 0


class TestSynthetic:
    def test_bull_then_bear_underlying_runs(self):
        # underlying falls then rises → bear→bull transition fires entries; the
        # synthetic premium is BS-priced. Just assert it executes and accounts costs.
        path = list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))
        ts, o, h, l, c = _ohlc(path)
        cfg = SterlingKiteEngineConfig(trail_target="mid")
        run = bt.run_synthetic(
            timestamps_ms=ts, u_open=o, u_high=h, u_low=l, u_close=c, cfg=cfg,
            trail_target="mid", iv=0.18, dte_days=7, bars_per_day=6,
            moneyness_offset_pct=0.0, qty=50, costs=bt.OptionCosts(),
            starting_capital=100_000)
        assert run.mode == "synthetic"
        assert "MODELED" in run.caveat  # honesty caveat present
        assert run.stats.trades >= 1
        for t in run.trades:
            assert t.costs > 0  # every trade carries real Indian charges
            assert t.entry_premium >= 0 and t.exit_premium >= 0

    def test_synthesize_premium_decays_with_theta(self):
        # flat underlying → premium must DECAY as DTE shrinks (theta)
        flat = [100.0] * 30
        prem = bt.synthesize_premium(
            underlying_close=flat, strike=100, iv=0.2, dte_days_start=10,
            bars_per_day=6, option_type="CE")
        assert prem[0] > prem[-1]  # later bar = less time value


class TestExitMode:
    def test_looser_mode_trades_no_more_than_tighter(self):
        # Oscillating premium: a tighter exit (one_red) re-enters on every pullback;
        # a looser exit (three_red) holds through minor dips → fewer, longer trades.
        seg = list(np.linspace(80, 170, 26)) + list(np.linspace(170, 95, 22))
        path = seg * 4
        ts, o, h, l, c = _ohlc(path)
        cfg = SterlingKiteEngineConfig()

        def trades_for(mode):
            run = bt.replay_premium_series(
                timestamps_ms=ts, premium_open=o, premium_high=h, premium_low=l,
                premium_close=c, cfg=cfg, trail_target="fast", exit_mode=mode, qty=50,
                costs=bt.OptionCosts(), starting_capital=100_000)
            return run.stats.trades

        one, three = trades_for("one_red"), trades_for("three_red")
        assert one >= 1 and three >= 1
        # tighter exit ⇒ at least as many trades as the looser one (monotonic)
        assert one >= three
