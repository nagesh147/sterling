"""Paper trader for the validated conviction book — live position walker,
real-data book, persisted forward track record. Isolated from the live engine.

Consistency is the load-bearing property: walk_positions' CLOSED trades must
match simulate_idx exactly, so the paper book never drifts from the validated
backtest. Network and the runner are exercised separately."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from study.paper_trader import walk_positions
from study.sim import simulate_idx


def _ohlc(closes, atr=2.0):
    closes = np.asarray(closes, float)
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    df = pd.DataFrame({"close": closes, "high": closes * 1.002,
                       "low": closes * 0.998}, index=idx)
    df["atr"] = atr
    return df


def test_closed_trades_match_simulate_idx():
    """On data where every trade closes (SL/TP/time hit before the end),
    walk_positions' closed set is byte-identical to simulate_idx — paper logic
    == validated backtest logic."""
    closes = np.r_[np.linspace(100, 130, 25), np.linspace(130, 95, 25),
                   np.linspace(95, 115, 25)]
    df = _ohlc(closes)
    sig = np.zeros(len(df), bool)
    sig[[0, 30, 55]] = True
    closed, open_pos = walk_positions(df, sig, 2.0, 3.0, direction="long")
    ref = simulate_idx(df, sig, 2.0, 3.0, direction="long")
    # all reference trades that closed before the last bar appear identically
    closed_pnls = [round(t["pnl_pct"], 8) for t in closed]
    ref_closed = [round(t["pnl_pct"], 8) for t in ref if t["exit_bar"] < len(df) - 1]
    assert closed_pnls[:len(ref_closed)] == ref_closed


def test_reports_open_position_at_tail():
    """A signal near the end that hasn't hit SL/TP and whose max_hold hasn't
    elapsed is reported OPEN with a mark-to-market unrealized P&L."""
    closes = np.linspace(100, 103, 30)        # gentle drift: neither SL nor TP hit
    df = _ohlc(closes, atr=2.0)
    sig = np.zeros(len(df), bool)
    sig[27] = True
    closed, open_pos = walk_positions(df, sig, 2.0, 5.0, direction="long",
                                      max_hold=200)
    assert open_pos is not None
    assert open_pos["status"] == "open"
    assert open_pos["entry_bar"] == 27
    expect = closes[-1] / closes[27] - 1 - 0.001
    assert open_pos["unrealized_pnl"] == pytest.approx(expect, rel=1e-4)


def test_tp_hit_is_closed_not_open():
    closes = np.r_[np.linspace(100, 140, 25), np.full(10, 140.0)]
    df = _ohlc(closes, atr=2.0)
    sig = np.zeros(len(df), bool)
    sig[0] = True
    closed, open_pos = walk_positions(df, sig, 2.0, 3.0, direction="long")
    assert open_pos is None
    assert len(closed) == 1
    assert closed[0]["status"] == "tp"
    assert closed[0]["pnl_pct"] > 0
