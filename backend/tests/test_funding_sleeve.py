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


from study.funding_sleeve import funding_cashflow, build_funding_trades


def test_funding_cashflow_sign_and_magnitude():
    # held from bar 1 to bar 4; settlements on bars 2 and 4 are 0.01 each.
    f_bar = pd.Series([0.0, 0.0, 0.01, 0.0, 0.01, 0.0])
    # SHORT collects positive funding: +0.02 over the two settlements after entry.
    assert funding_cashflow(f_bar, 1, 4, "short") == pytest.approx(0.02)
    # LONG pays it: -0.02.
    assert funding_cashflow(f_bar, 1, 4, "long") == pytest.approx(-0.02)
    # The entry bar's own settlement (bar 1) is excluded; exit bar (4) included.
    assert funding_cashflow(f_bar, 0, 2, "short") == pytest.approx(0.01)


def test_build_funding_trades_tags_and_adds_cashflow():
    bars = _bars(n=40)
    rates = [0.0] * 4 + [0.02] * 16         # sustained rich funding => shorts
    f = _funding(start="2024-01-01 00:00", n=20, rates=rates)
    trades = build_funding_trades("BTC", bars, f, window=3, thr=1.0,
                                  exit_mode="bracket")
    assert trades, "expected at least one funding trade"
    t = trades[0]
    assert t["symbol"] == "BTC_FUND"
    assert t["sleeve"] == "funding"
    assert t["direction"] in ("long", "short")
    assert {"entry_time", "exit_time", "pnl_pct", "stop_dist_pct"} <= set(t)
    assert t["stop_dist_pct"] > 0
