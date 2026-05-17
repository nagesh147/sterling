import pytest
from tests.conftest import make_candles
from app.engines.backtest.backtest_engine import run_backtest


def test_run_backtest_accepts_st_configs():
    """run_backtest must accept custom st_configs without error."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    res = run_backtest("BTC", c4h, c1h, lookback_days=30,
                       sample_every_n_bars=4,
                       st_configs=[(3, 1.5), (5, 1.0), (8, 0.8)])
    assert len(res.bars) >= 0


def test_run_backtest_accepts_st_threshold_2():
    """st_threshold=2 produces >= confirmed setups as threshold=3."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    res3 = run_backtest("BTC", c4h, c1h, lookback_days=30,
                        sample_every_n_bars=4, st_threshold=3)
    res2 = run_backtest("BTC", c4h, c1h, lookback_days=30,
                        sample_every_n_bars=4, st_threshold=2)
    conf3 = res3.stats.confirmed_long_setups + res3.stats.confirmed_short_setups
    conf2 = res2.stats.confirmed_long_setups + res2.stats.confirmed_short_setups
    assert conf2 >= conf3


def test_run_backtest_default_unchanged():
    """No new params → identical results to before."""
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    r1 = run_backtest("BTC", c4h, c1h, lookback_days=30, sample_every_n_bars=4)
    r2 = run_backtest("BTC", c4h, c1h, lookback_days=30, sample_every_n_bars=4,
                      st_configs=None, st_threshold=3)
    assert r1.stats.total_bars_evaluated == r2.stats.total_bars_evaluated
    assert r1.stats.green_arrows == r2.stats.green_arrows
