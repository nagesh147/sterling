"""Reconcile the live ma_crossover with the scalping backtest.

The live scanner calls evaluate_ma_crossover with a real 1h series (it gates
entries on 1h structure via check_1h_structure). The bar-replay engine called
it with only 5 args (no candles_1h) → it CRASHED, so the live ma_crossover was
never validated by the scalping backtest. This pins the fix: the replay derives
a 1h series from the 15m exec candles and the strategy runs end-to-end.
"""
from __future__ import annotations

import numpy as np

from app.schemas.market import Candle
from app.engines.scalping.config import ScalpingProfile
from app.engines.scalping.backtest import (
    run_scalping_backtest, _resample_15m_to_1h, EVALUATORS,
)


def _c(ts_ms, o, h, l, cl, v=100.0):
    return Candle(timestamp_ms=ts_ms, open=o, high=h, low=l, close=cl, volume=v)


def test_resample_15m_to_1h_aggregates_ohlc():
    base = 1_700_000_000_000  # arbitrary ms aligned to an hour is not required
    # four 15m bars inside one hour bucket
    h = 3_600_000
    q = 900_000
    start = (base // h) * h
    bars = [
        _c(start + 0 * q, 100, 110, 95, 105),
        _c(start + 1 * q, 105, 120, 104, 108),
        _c(start + 2 * q, 108, 109, 90, 92),
        _c(start + 3 * q, 92, 100, 91, 99),
    ]
    out = _resample_15m_to_1h(bars)
    assert len(out) == 1
    b = out[0]
    assert b.open == 100 and b.close == 99
    assert b.high == 120 and b.low == 90
    assert b.volume == 400.0


def test_ma_crossover_adapter_is_5arg_and_runs():
    """The EVALUATORS entry must accept the uniform 5-arg replay signature and
    call through to the real evaluator without raising."""
    fn = EVALUATORS["ma_crossover"]
    q = 900_000
    start = 1_700_000_000_000
    exec_15m = [_c(start + i * q, 100, 101, 99, 100.0) for i in range(80)]
    macro_4h = [_c(start + i * 4 * 3_600_000, 100, 101, 99, 100.0) for i in range(40)]
    cfg = ScalpingProfile()
    # Must not raise TypeError (the original bug); returns a signal-like object.
    sig = fn("BTC", macro_4h, exec_15m, [], cfg)
    assert hasattr(sig, "entry_ok")


def test_run_backtest_with_ma_crossover_does_not_crash():
    """End-to-end: ma_crossover is replayable in the scalping backtest."""
    q = 900_000
    start = 1_700_000_000_000
    n = 800
    # gentle trend so MAs and levels are well-defined; no assertion on trade count
    closes = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.2, n))
    exec_15m = [_c(start + i * q, c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]
    m = 200
    mcloses = 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.4, m))
    macro_4h = [_c(start + i * 4 * 3_600_000, c, c + 1, c - 1, c) for i, c in enumerate(mcloses)]
    cfg = ScalpingProfile(macro_timeframe="4h", execution_timeframe="15m")
    out = run_scalping_backtest("BTC", macro_4h, exec_15m, cfg, ["ma_crossover"])
    assert out.total_trades >= 0  # the point is: it completed without TypeError
