"""Funding sleeve — alignment, leak-free z-score signal, cash-flow, trades."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from study.funding_sleeve import align_funding, funding_signal


def _bars(start="2024-01-01 00:00", n=24, freq="4h"):
    idx = pd.date_range(start, periods=n, freq=freq)
    px = 100.0 * (1 + 0.001 * np.arange(n))
    return pd.DataFrame({"open": px, "high": px * 1.01, "low": px * 0.99,
                         "close": px * 1.002, "volume": 1.0,
                         "atr": px * 0.02}, index=idx)


def _funding(start="2024-01-01 00:00", n=8, freq="8h", rates=None):
    idx = pd.date_range(start, periods=n, freq=freq)
    if rates is None:
        rates = [0.0001] * n
    return pd.Series(rates, index=idx, name="funding_rate")


def test_align_funding_lands_events_on_bar_opens():
    bars = _bars(n=6)                       # 00,04,08,12,16,20
    f = _funding(n=2)                       # 00:00, 08:00
    a = align_funding(f, bars.index)
    assert len(a) == len(bars)
    assert a.loc["2024-01-01 00:00"] == 0.0001
    assert a.loc["2024-01-01 08:00"] == 0.0001
    assert a.loc["2024-01-01 04:00"] == 0.0   # no settlement on this 4h bar


def test_funding_signal_is_leak_free():
    # signal at bar t must use only funding events with time <= t.
    bars = _bars(n=24)
    f = _funding(n=8, rates=[0.0, 0.0, 0.0, 0.0, 0.01, 0.01, 0.01, 0.01])
    sig = funding_signal(f, bars.index, window=3, thr=1.0)
    assert len(sig) == len(bars)
    # The early bars (before any high-funding events accrue) cannot be short.
    assert sig.iloc[0] == 0
    # Truncating future funding must not change earlier signal values.
    sig_trunc = funding_signal(f.iloc[:5], bars.index, window=3, thr=1.0)
    common = sig.index.intersection(sig_trunc.index)
    early = common[common <= f.index[4]]
    assert (sig.loc[early].fillna(0) == sig_trunc.loc[early].fillna(0)).all()


def test_funding_signal_sign_convention():
    # Richly POSITIVE funding (crowd long) => contrarian SHORT (sig == -1).
    bars = _bars(n=24)
    rates = [0.0] * 4 + [0.02] * 4          # jump to very positive
    f = _funding(n=8, rates=rates)
    sig = funding_signal(f, bars.index, window=3, thr=1.0)
    assert sig.min() == -1                  # produced a short
    assert sig.max() <= 1
    # Deeply NEGATIVE funding (crowd short) => contrarian LONG (sig == +1).
    f2 = _funding(n=8, rates=[0.0] * 4 + [-0.02] * 4)
    sig2 = funding_signal(f2, bars.index, window=3, thr=1.0)
    assert sig2.max() == 1
