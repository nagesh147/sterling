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


# --- per-symbol paper sleeves + book ------------------------------------
from study.paper_trader import build_paper_sleeves, paper_book, PAPER_CONFIG


def _trending_frame(n=400, seed=1):
    rng = np.random.default_rng(seed)
    c = np.clip(100 + np.cumsum(rng.normal(0.05, 1.0, n)), 10, None)
    idx = pd.date_range("2024-06-01", periods=n, freq="4h")
    df = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99,
                       "close": c, "volume": 1.0}, index=idx)
    df["atr"] = (df["high"] - df["low"]).rolling(14).mean().bfill()
    return df


def test_build_paper_sleeves_tags_and_times():
    df = _trending_frame()
    closed, opens = build_paper_sleeves("BTCUSD", df, PAPER_CONFIG)
    assert all(t["symbol"] == "BTCUSD" for t in closed)
    assert all({"entry_time", "exit_time", "pnl_pct", "sleeve", "stop_dist_pct"}
               <= t.keys() for t in closed)
    for op in opens:                                  # opens carry live levels
        assert {"entry_time", "unrealized_pnl", "sleeve", "stop_dist_pct"} <= op.keys()


def test_paper_book_realized_matches_validated_sizing():
    """Realized equity must equal portfolio_equity_sized over the same closed
    trades — paper never drifts from the validated backtest."""
    from study.regime_book import portfolio_equity_sized
    frames = {s: _trending_frame(seed=i) for i, s in
              enumerate(("BTCUSD", "ETHUSD", "SOLUSD"))}
    inception = pd.Timestamp("2024-06-01")
    book = paper_book(frames, PAPER_CONFIG, inception=inception, capital=500.0)
    # rebuild realized independently
    closed = []
    for s, df in frames.items():
        c, _ = build_paper_sleeves(s, df, PAPER_CONFIG)
        closed += [t for t in c if t["entry_time"] >= inception]
    ref = portfolio_equity_sized(
        closed, 500.0, PAPER_CONFIG["risk_per_trade"], PAPER_CONFIG["max_leverage"],
        PAPER_CONFIG["max_concurrent"], PAPER_CONFIG["leverage"])
    assert book["realized"]["end"] == pytest.approx(ref["end"], rel=1e-9)
    assert {"realized", "open_positions", "total_equity", "n_closed"} <= book.keys()


def test_state_round_trip(tmp_path):
    from study.paper_trader import save_state, load_state
    book = {
        "realized": {"end": 612.0, "ret": 0.224, "sharpe": 1.1, "max_dd": -0.2,
                     "n": 18, "weighted_pnls": [0.01, -0.02], "avg_lev": 0.5},
        "open_positions": [{"symbol": "BTCUSD", "sleeve": "mr", "direction": "long",
                            "entry_time": pd.Timestamp("2026-06-01"),
                            "unrealized_pnl": 0.03, "weight": 0.4}],
        "total_equity": 640.0, "n_closed": 18,
        "inception": pd.Timestamp("2025-09-07"), "capital": 500.0,
    }
    p = tmp_path / "state.json"
    save_state(book, str(p))
    st = load_state(str(p))
    assert st["n_closed"] == 18
    assert st["total_equity"] == pytest.approx(640.0)
    assert st["realized"]["end"] == pytest.approx(612.0)
    assert st["open_positions"][0]["symbol"] == "BTCUSD"
    assert load_state(str(tmp_path / "absent.json")) is None
