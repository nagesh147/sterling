"""Termination + correctness for comprehensive_backtest.simulate().

The sequential simulator must always advance its bar index. A regression made
it spin forever on the first flat bar with no signal (position==0, signals[i]
False) because neither branch incremented `i` — which silently hangs the entire
270-config edge study. These tests pin termination and basic fill correctness.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import comprehensive_backtest as cb


def _df(closes, atr=1.0):
    closes = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "open": closes,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "atr": np.full(len(closes), atr, dtype=float),
    })


def test_terminates_with_no_signals():
    # All-False signals + valid ATR is the exact infinite-loop trigger.
    df = _df([100.0] * 50)
    signals = np.zeros(50, dtype=bool)
    out = cb.simulate(df, signals, {"sl_mult": 2.0, "tp_mult": 3.5}, profile_name="Intraday")
    assert out["trades"] == []


def test_books_one_trade_on_signal_then_take_profit():
    # Entry at bar 2 (close 100); TP = 100 + 3.5*ATR(1) = 103.5; then flat bars
    # afterwards must not hang.
    closes = [100, 100, 100, 101, 102, 103, 105, 100, 100, 100] + [100] * 20
    df = _df(closes)
    signals = np.zeros(len(closes), dtype=bool)
    signals[2] = True
    out = cb.simulate(df, signals, {"sl_mult": 2.0, "tp_mult": 3.5}, profile_name="Intraday")
    assert len(out["trades"]) == 1
    t = out["trades"][0]
    assert t["entry"] == 100.0
    assert abs(t["exit"] - 103.5) < 1e-9   # exited at the take-profit level
