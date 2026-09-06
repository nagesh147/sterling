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


def test_backtest_and_live_scanner_resolve_the_same_exit_bar():
    """The replay's exit loop and the live scanner's must not drift.

    The backtest carried its own red-count-only copy, annotated "identical to the live
    scanner.is_active loop" — accurate when written, and silently wrong the moment the
    live loop started enforcing the trailing stop. Both now go through
    ``sterling_kite_engine.exits``, and this pins that.
    """
    import numpy as np

    from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
    from app.engines.sterling_kite_engine.exits import resolve_exit
    from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
    from app.services.kite_engine.backtest import _exit_bar

    close = (list(np.linspace(300.0, 150.0, 60)) + list(np.linspace(150.0, 600.0, 80))
             + list(np.linspace(595.0, 300.0, 8)))
    c = np.asarray(close, float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + 1.0
    l = np.minimum(o, c) - 1.0

    cfg = SterlingKiteEngineConfig(exit_mode="three_red_signal", trail_target="fast")
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    n = len(c)
    entries = [int(i) for i in np.where(longs)[0]]
    assert entries, "expected at least one long entry"

    for entry_i in entries:
        live_i, live_reason = resolve_exit(r, "long", entry_i, n - 1, cfg, longs, shorts)
        bt_i, bt_reason = _exit_bar(r, entry_i, 1, longs, shorts, cfg.exit_mode, n,
                                    cfg, cfg.trail_target)
        expected_i = (n - 1) if live_i is None else live_i
        assert bt_i == expected_i
        assert bt_reason == (live_reason or "series end")


class TestShortSideReplay:
    """A sign error on the short path produces a plausible equity curve that no
    order could have made, so each of the three things that differ is asserted
    separately rather than trusting the aggregate."""

    @staticmethod
    def _run(path, side, **kw):
        ts, o, h, l, c = _ohlc(path)
        cfg = SterlingKiteEngineConfig(trail_target="mid")
        return bt.replay_premium_series(
            timestamps_ms=ts, premium_open=o, premium_high=h, premium_low=l,
            premium_close=c, cfg=cfg, trail_target="mid", qty=50,
            costs=bt.FuturesCosts(slippage_pct=0.0), starting_capital=10_000_000,
            side=side, **kw)

    def test_an_unknown_side_is_refused(self):
        with pytest.raises(ValueError, match="side must be"):
            self._run(list(np.linspace(100, 200, 140)), "sideways")

    def test_the_default_side_is_long_and_unchanged(self):
        path = list(np.linspace(120, 60, 50)) + list(np.linspace(60, 300, 90))
        ts, o, h, l, c = _ohlc(path)
        cfg = SterlingKiteEngineConfig(trail_target="mid")
        kw = dict(timestamps_ms=ts, premium_open=o, premium_high=h, premium_low=l,
                  premium_close=c, cfg=cfg, trail_target="mid", qty=50,
                  costs=bt.OptionCosts(), starting_capital=100_000)
        assert (bt.replay_premium_series(**kw).stats.trades
                == bt.replay_premium_series(**kw, side="long").stats.trades)

    def test_a_short_enters_on_the_down_transition_not_the_up_one(self):
        # Rises then falls: the FALL is what arms a short. A long has nothing to
        # ride here, so taking the same entries would be the tell.
        path = list(np.linspace(100, 260, 60)) + list(np.linspace(260, 90, 90))
        short = self._run(path, "short")
        assert short.stats.trades >= 1
        assert all(t.direction == "short" for t in short.trades)
        assert short.stats.net_pnl > 0

    def test_long_and_short_never_enter_on_the_same_bar(self):
        """They read different transition arrays. If a sign slip made the short
        path read ``longs``, the two would agree on entries and the short would
        just be a mirrored long — profitable on exactly the moves a long is."""
        path = (list(np.linspace(120, 60, 50)) + list(np.linspace(60, 300, 70))
                + list(np.linspace(300, 110, 70)))
        longs = {t.entry_ms for t in self._run(path, "long").trades}
        shorts = {t.entry_ms for t in self._run(path, "short").trades}
        assert longs and shorts
        assert not (longs & shorts)

    def test_short_pnl_is_entry_minus_exit(self):
        path = list(np.linspace(100, 260, 60)) + list(np.linspace(260, 90, 90))
        run = self._run(path, "short")
        assert run.trades
        for t in run.trades:
            # The reported prices are rounded to paise; the PnL is not. Allow the
            # half-paise each side can carry, scaled by size — no more.
            tol = 0.005 * 2 * t.qty
            assert t.gross_pnl == pytest.approx(
                (t.entry_premium - t.exit_premium) * t.qty, abs=tol)
            assert t.gross_pnl != pytest.approx(
                (t.exit_premium - t.entry_premium) * t.qty, abs=tol) or t.gross_pnl == 0

    def test_a_short_stop_fills_no_better_than_the_gap(self):
        """A long's stop is below price and fills at the MINIMUM of open and level;
        a short's is above and must fill at the MAXIMUM. Taking the minimum on a
        short would hand every gapped exit a fill better than the market offered."""
        import re
        # Each side needs a path that actually rebounds against it: a short is
        # stopped by a rally, a long by a selloff.
        rebound_up = (list(np.linspace(100, 260, 60)) + list(np.linspace(260, 90, 60))
                      + list(np.linspace(90, 240, 60)))
        rebound_down = (list(np.linspace(120, 60, 50)) + list(np.linspace(60, 300, 70))
                        + list(np.linspace(300, 130, 70)))
        for side, path, ok in (("short", rebound_up, lambda px, lvl: px >= lvl - 1e-6),
                               ("long", rebound_down, lambda px, lvl: px <= lvl + 1e-6)):
            run = self._run(path, side)
            breaches = [t for t in run.trades if t.exit_reason.startswith("trail breach")]
            assert breaches, f"{side}: the path must breach at least one trail"
            for t in breaches:
                level = float(re.search(r"([0-9.]+)\)", t.exit_reason).group(1))
                assert ok(t.exit_premium, level), (side, t.exit_premium, level)
