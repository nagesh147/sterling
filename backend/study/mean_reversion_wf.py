"""Anchored walk-forward parameter search for the mean-reversion sleeve.

RESEARCH TOOL — not wired into anything live. It answers one honest question:
does a *fresh* Bollinger+RSI mean-reversion parameter search produce a FORWARD
(out-of-sample) edge, or does it just overfit like everything else?

Method (no lookahead):
  * Build every param variant once on the full series (signals use only past
    bars via .shift, so a single pass is leak-free).
  * Anchored walk-forward: for each test window, select the best variant on
    trades ENTERED STRICTLY BEFORE the window (`select_best`), then trade the
    window. Stitch the window trades into one out-of-sample stream.
  * Deflate the stitched OOS Sharpe by the grid size (multiple-testing).

2026-06-07 finding (BTC/ETH/SOL, 4h): the edge is REAL but UNPROVABLE here —
positive OOS, beats buy-and-hold, generalises cross-symbol, yet only ~1.5
trades/month at the timeframes where it works (n<=23 → DSR ~0.01-0.04 << 0.5).
Dropping to 1h to gain trades kills the edge. See
docs/mean_reversion_sleeve_plan.md for the multi-symbol path to a provable n.

Run:  python backend/study/mean_reversion_wf.py
"""
from __future__ import annotations

import glob
import itertools
import os

import numpy as np
import pandas as pd

from app.engines.edge.strategies import resample
from app.engines.edge.robustness import deflated_sharpe_ratio
from study.sim import simulate_idx, sharpe as _sharpe

FEE_RT = 0.001
MAX_HOLD = 200
# (sl_mult, tp_mult) — kept local so the tool has no live-config coupling.
PROFILES = {"Scalping": (1.0, 2.0), "Intraday": (2.0, 3.5), "Aggressive": (1.5, 4.5)}


def bb_rsi_signals(df: pd.DataFrame, bb_lk: int, bb_std: float,
                   rsi_p: int, rsi_th: float) -> np.ndarray:
    """Buy when price reclaims the lower Bollinger band while RSI is oversold.
    Long-only, vectorised, no lookahead (.shift on the cross)."""
    c = df["close"]
    d = c.diff()
    gain = d.clip(lower=0).rolling(rsi_p).mean()
    loss = (-d.clip(upper=0)).rolling(rsi_p).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sma = c.rolling(bb_lk).mean()
    std = c.rolling(bb_lk).std()
    lower = sma - bb_std * std
    reclaim = (c > lower) & (c.shift(1) <= lower.shift(1))
    return (reclaim & (rsi < rsi_th)).fillna(False).to_numpy()


def default_grid():
    """243 variants: BB lookback × BB std × RSI period × RSI threshold × profile."""
    return list(itertools.product(
        [20, 30, 50], [2.0, 2.5, 3.0], [2, 7, 14], [30, 40, 50], PROFILES.keys()))


def build_combos(df: pd.DataFrame, grid) -> list[tuple]:
    """Simulate every variant once; tag each trade with its entry timestamp.
    Returns [(params, frame)] where frame has pnl_pct + entry_time."""
    combos = []
    for bb_lk, bb_std, rsi_p, rsi_th, prof in grid:
        sl, tp = PROFILES[prof]
        tr = simulate_idx(df, bb_rsi_signals(df, bb_lk, bb_std, rsi_p, rsi_th),
                          sl, tp, direction="long", fee_rt=FEE_RT, max_hold=MAX_HOLD)
        if not tr:
            continue
        f = pd.DataFrame(tr)
        f["entry_time"] = df.index[f["entry_bar"].to_numpy()]
        combos.append(((bb_lk, bb_std, rsi_p, rsi_th, prof), f))
    return combos


def select_best(combos, train_cutoff, min_train_trades: int = 20):
    """Pick the highest-Sharpe variant on trades ENTERED STRICTLY BEFORE
    `train_cutoff`. Trades at/after the cutoff are invisible — this is the
    no-lookahead guarantee. Returns (params, frame) or None."""
    best = None
    for params, f in combos:
        train = f[f["entry_time"] < train_cutoff]
        if len(train) < min_train_trades:
            continue
        s = _sharpe(train["pnl_pct"].tolist())
        if best is None or s > best[0]:
            best = (s, params, f)
    return None if best is None else (best[1], best[2])


def walk_forward(combos, t0, t1, n_folds: int = 5,
                 oos_start: float = 0.5, min_train_trades: int = 20) -> dict:
    """Anchored WF over n_folds equal windows spanning [oos_start, 1.0] of the
    calendar. Each window is traded by the variant selected on all prior data."""
    span = t1 - t0
    width = (1.0 - oos_start) / n_folds
    oos_pnls, picks = [], []
    for k in range(n_folds):
        ts = t0 + span * (oos_start + width * k)
        te = t0 + span * (oos_start + width * (k + 1))
        sel = select_best(combos, ts, min_train_trades)
        if sel is None:
            picks.append({"test_end": te, "params": None, "n": 0})
            continue
        params, f = sel
        seg = f[(f["entry_time"] >= ts) & (f["entry_time"] < te)]
        oos_pnls += seg["pnl_pct"].tolist()
        picks.append({"test_end": te, "params": params, "n": int(len(seg))})
    return {"oos_pnls": oos_pnls, "picks": picks}


def equity_stats(pnls, cap: float = 500.0) -> dict:
    if not pnls:
        return {"end": cap, "ret": 0.0, "sharpe": 0.0, "max_dd": 0.0, "n": 0}
    a = np.asarray(pnls, float)
    eq = cap * np.cumprod(1 + a)
    peak = np.maximum.accumulate(eq)
    return {"end": float(eq[-1]), "ret": float(eq[-1] / cap - 1.0),
            "sharpe": _sharpe(list(a)), "max_dd": float(((eq - peak) / peak).min()),
            "n": int(len(a))}


def run_symbol(df: pd.DataFrame, grid=None, cap: float = 500.0) -> dict:
    grid = grid or default_grid()
    combos = build_combos(df, grid)
    t0, t1 = df.index[0], df.index[-1]
    wf = walk_forward(combos, t0, t1)
    stats = equity_stats(wf["oos_pnls"], cap)
    stats["dsr"] = deflated_sharpe_ratio(wf["oos_pnls"], num_trials=len(combos)) \
        if wf["oos_pnls"] else 0.0
    stats["picks"] = wf["picks"]
    stats["n_variants"] = len(combos)
    # HODL over the same OOS span for reference.
    oos_start_t = t0 + (t1 - t0) * 0.5
    sub = df["close"][df.index >= oos_start_t]
    stats["hodl_end"] = cap * float(sub.iloc[-1] / sub.iloc[0]) if len(sub) > 1 else cap
    return stats


def main():
    cap = 500.0
    files = sorted(glob.glob("vector_store_1m_*.parquet"))
    if not files:
        print("No vector_store_1m_*.parquet found (run from backend/).")
        return
    print(f"Mean-reversion walk-forward · {len(default_grid())} variants · ${cap:.0f}\n")
    print(f"{'symbol':>8}{'TF':>5}{'WF $':>9}{'WF %':>8}{'Sharpe':>8}{'maxDD':>8}"
          f"{'n':>5}{'DSR':>8}   vs HODL")
    print("-" * 78)
    for f in files:
        sym = os.path.basename(f).replace("vector_store_1m_", "").replace(".parquet", "")
        df1 = pd.read_parquet(f, columns=["time", "open", "high", "low", "close", "volume"])
        df1["time"] = pd.to_datetime(df1["time"], unit="s")
        df1 = df1.set_index("time").sort_index()
        for rule, tf in [("2h", "2h"), ("4h", "4h")]:
            s = run_symbol(resample(df1, rule), cap=cap)
            print(f"{sym:>8}{tf:>5}{s['end']:>9,.0f}{s['ret']*100:>7.1f}%"
                  f"{s['sharpe']:>8.2f}{s['max_dd']*100:>7.1f}%{s['n']:>5}{s['dsr']:>8.4f}"
                  f"   ${s['hodl_end']:,.0f}")
    print("\nReminder: DSR << 0.5 means NOT deployable. See "
          "docs/mean_reversion_sleeve_plan.md for the multi-symbol path to a "
          "provable sample size.")


if __name__ == "__main__":
    main()
