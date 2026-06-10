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


from study.funding_sleeve import simulate_hold_to_flip


def test_hold_to_flip_exits_when_signal_leaves_target():
    # sig holds target=+1 for bars 2..5 then drops to 0 → exit at bar 6.
    idx = pd.date_range("2024-01-01", periods=10, freq="4h")
    px = np.array([100, 100, 100, 101, 102, 103, 104, 104, 104, 104], float)
    df = pd.DataFrame({"open": px, "high": px, "low": px, "close": px,
                       "volume": 1.0, "atr": 2.0}, index=idx)
    sig = np.array([0, 0, 1, 1, 1, 1, 0, 0, 0, 0])
    raw = simulate_hold_to_flip(df, sig, target=1, fee_rt=0.0, max_hold=200)
    assert len(raw) == 1
    t = raw[0]
    assert t["entry_bar"] == 2 and t["exit_bar"] == 6
    # long pnl over 100 -> 104, no fee:
    assert t["pnl_pct"] == pytest.approx(0.04)


def test_hold_to_flip_short_direction_and_fee():
    idx = pd.date_range("2024-01-01", periods=8, freq="4h")
    px = np.array([100, 100, 100, 98, 96, 96, 96, 96], float)
    df = pd.DataFrame({"open": px, "high": px, "low": px, "close": px,
                       "volume": 1.0, "atr": 2.0}, index=idx)
    sig = np.array([0, 0, -1, -1, 0, 0, 0, 0])
    raw = simulate_hold_to_flip(df, sig, target=-1, fee_rt=0.001, max_hold=200)
    assert len(raw) == 1
    t = raw[0]
    assert t["entry_bar"] == 2 and t["exit_bar"] == 4
    # short 100 -> 96 = +0.04 price, minus 0.001 fee:
    assert t["pnl_pct"] == pytest.approx(0.039)


from study.funding_sleeve import funding_grid, select_funding_sleeve


def test_funding_grid_is_eight_cells():
    g = funding_grid()
    assert len(g) == 8
    assert all(len(cell) == 3 for cell in g)          # (window, thr, exit_mode)
    assert {c[2] for c in g} == {"bracket", "flip"}


def test_select_funding_sleeve_is_lookahead_free_and_shaped():
    # Two synthetic symbols with sustained funding regimes so trades exist.
    frames, fundings = {}, {}
    for coin, base in (("BTC", 100.0), ("ETH", 50.0)):
        bars = _bars(start="2024-01-01", n=400)
        bars["close"] = base * (1 + 0.0005 * np.arange(400))
        bars["high"] = bars["close"] * 1.01
        bars["low"] = bars["close"] * 0.99
        bars["atr"] = bars["close"] * 0.02
        frames[f"{coin}USD"] = bars
        rates = ([0.0] * 100 + [0.03] * 100 + [0.0] * 100 + [-0.03] * 100)
        fundings[coin] = _funding(start="2024-01-01", n=200,
                                  rates=[rates[i] for i in range(0, 400, 2)])
    res = select_funding_sleeve(frames, fundings, oos_start=0.5)
    assert set(res) >= {"chosen", "scored", "dsr", "n_grid", "is_oos_corr"}
    assert res["n_grid"] == 8
    assert 0.0 <= res["dsr"] <= 1.0
    assert "oos_trades" in res["chosen"]


from study.funding_sleeve import returns_by_bar, combine_books


def test_returns_by_bar_buckets_pnl_on_exit():
    idx = pd.date_range("2024-01-01", periods=5, freq="4h")
    trades = [
        {"exit_time": idx[1], "pnl_pct": 0.02},
        {"exit_time": idx[1], "pnl_pct": -0.01},   # two exits same bar → summed
        {"exit_time": idx[3], "pnl_pct": 0.05},
    ]
    s = returns_by_bar(trades, idx)
    assert len(s) == 5
    assert s.iloc[1] == pytest.approx(0.01)
    assert s.iloc[3] == pytest.approx(0.05)
    assert s.iloc[0] == 0.0


def test_combine_books_pools_and_reports_corr_and_dsr():
    idx = pd.date_range("2024-01-01", periods=20, freq="4h")
    book = [{"symbol": "BTCUSD", "entry_time": idx[i], "exit_time": idx[i + 1],
             "pnl_pct": 0.01, "stop_dist_pct": 0.03} for i in range(0, 10, 2)]
    fund = [{"symbol": "BTC_FUND", "entry_time": idx[i], "exit_time": idx[i + 1],
             "pnl_pct": 0.008, "stop_dist_pct": 0.03} for i in range(1, 11, 2)]
    res = combine_books(book, fund, idx, book_trials=36, funding_trials=8)
    assert set(res) >= {"combined", "rho", "dsr_total", "dsr_funding_only", "n"}
    assert res["combined"]["n"] == len(book) + len(fund)
    assert -1.0 <= res["rho"] <= 1.0
    assert 0.0 <= res["dsr_total"] <= 1.0


def test_combine_with_no_funding_equals_book_alone():
    # With zero funding trades, the combined book must equal the book alone
    # (cap 6 vs the book's own concurrency does not change a <=3-name book).
    idx = pd.date_range("2024-01-01", periods=20, freq="4h")
    book = [{"symbol": "BTCUSD", "entry_time": idx[i], "exit_time": idx[i + 1],
             "pnl_pct": 0.01, "stop_dist_pct": 0.03} for i in range(0, 10, 2)]
    res = combine_books(book, [], idx, book_trials=36, funding_trials=8)
    from study.regime_book import portfolio_equity_sized
    book_only = portfolio_equity_sized(book, 500.0, 0.015, 3.0, 6, 1.0)
    assert res["combined"]["weighted_pnls"] == book_only["weighted_pnls"]
    assert res["rho"] == 0.0
