"""Funding-rate positioning-tilt sleeve — the orthogonal-information spike.

Turns Binance perp funding into a leak-free CONTRARIAN directional signal (richly
positive funding = over-leveraged longs → short bias; deeply negative → long),
runs it through the existing study.sim.simulate_idx fill engine with the real
funding cash-flow added per held bar, then pools its trades with the conviction
book's trades into the existing per-trade book machinery so combined Sharpe/DSR
stay comparable to the book's 1.15 / 0.166.

RESEARCH TOOL — not wired into anything live. Spec:
docs/superpowers/specs/2026-06-10-funding-sleeve-spike-design.md

Run:  cd backend && .venv/bin/python -m study.funding_sleeve
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from study.sim import simulate_idx, sharpe as _sharpe
from study.regime_book import (
    merge_portfolio, portfolio_equity_sized, _spearman,
)
from app.engines.edge.robustness import deflated_sharpe_ratio

FEE_RT = 0.001
MAX_HOLD = 200
_SL, _TP = 1.5, 4.5          # Aggressive bracket — same as the MR sleeve


def align_funding(funding: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Reindex 8h funding settlements onto the 4h bar grid: each settlement
    (00/08/16 UTC) lands on the bar whose open == the settlement time; bars with
    no settlement are 0.0. Used for per-bar cash-flow accrual."""
    return funding.reindex(index).fillna(0.0)


def funding_signal(funding: pd.Series, index: pd.DatetimeIndex,
                   window: int, thr: float) -> pd.Series:
    """Leak-free contrarian signal on the bar grid, in {-1, 0, +1}.

    The z-score is computed over the rolling window of the last `window` funding
    EVENTS (not bars), using only events with time <= the event itself; the
    resulting per-event signal is forward-filled onto bars, so the signal at bar
    t reflects only the most recent funding event with time <= t. No lookahead.

    Sign: z > +thr (funding richly positive, crowd long) → -1 (contrarian SHORT);
          z < -thr (funding deeply negative, crowd short) → +1 (contrarian LONG).
    """
    f = funding.sort_index()
    mean = f.rolling(window).mean()
    std = f.rolling(window).std()
    z = (f - mean) / std.replace(0.0, np.nan)
    sig_event = pd.Series(
        np.where(z > thr, -1, np.where(z < -thr, 1, 0)), index=f.index
    ).fillna(0).astype(int)
    return sig_event.reindex(index, method="ffill").fillna(0).astype(int)


def funding_cashflow(f_bar: pd.Series, entry_bar: int, exit_bar: int,
                     direction: str) -> float:
    """Funding cash-flow (as a fraction of notional) accrued holding from
    entry_bar to exit_bar. Entry is at the entry bar's close (after that bar's
    settlement), so settlements strictly after entry up to and including exit
    count: bars [entry_bar+1 .. exit_bar]. A SHORT collects positive funding; a
    LONG pays it."""
    if exit_bar <= entry_bar:
        return 0.0
    accrued = float(f_bar.iloc[entry_bar + 1: exit_bar + 1].sum())
    return accrued if direction == "short" else -accrued


def build_funding_trades(coin: str, df: pd.DataFrame, funding: pd.Series,
                         window: int, thr: float, exit_mode: str = "bracket"
                         ) -> list[dict]:
    """Build funding-sleeve trades for one symbol. The contrarian z-signal enters
    longs/shorts through the existing simulate_idx (bracket) fill engine; the real
    funding cash-flow is added to each trade's pnl. Trades are tagged with a
    distinct `{coin}_FUND` name + stop_dist_pct (for vol-target sizing)."""
    sig = funding_signal(funding, df.index, window, thr).to_numpy()
    f_bar = align_funding(funding, df.index)
    close = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    out: list[dict] = []
    for target, direction in ((1, "long"), (-1, "short")):
        sigs = (sig == target)
        if exit_mode == "bracket":
            raw = simulate_idx(df, sigs, _SL, _TP, direction=direction,
                               fee_rt=FEE_RT, max_hold=MAX_HOLD)
        else:                                # hold-to-flip
            raw = simulate_hold_to_flip(df, sig, target, fee_rt=FEE_RT,
                                        max_hold=MAX_HOLD)
        for t in raw:
            e = close[t["entry_bar"]]
            a = atr[t["entry_bar"]]
            fpnl = funding_cashflow(f_bar, t["entry_bar"], t["exit_bar"], direction)
            out.append({
                "symbol": f"{coin}_FUND", "sleeve": "funding", "direction": direction,
                "entry_time": df.index[t["entry_bar"]],
                "exit_time": df.index[t["exit_bar"]],
                "pnl_pct": t["pnl_pct"] + fpnl,
                "stop_dist_pct": (_SL * a / e) if e > 0 else 0.0,
            })
    return out


def simulate_hold_to_flip(df: pd.DataFrame, sig, target: int,
                          fee_rt: float = FEE_RT, max_hold: int = MAX_HOLD
                          ) -> list[dict]:
    """Signal-driven exit (NOT a simulate_idx bracket): enter at close on each bar
    where sig == target with no open position; exit at close of the first later
    bar where sig != target (or after max_hold / at the series end). Same fee
    model as simulate_idx. Returns {pnl_pct, entry_bar, exit_bar}."""
    close = df["close"].to_numpy(float)
    sig = np.asarray(sig)
    n = len(close)
    direction = "long" if target > 0 else "short"
    out: list[dict] = []
    i = 0
    while i < n - 1:
        if sig[i] != target:
            i += 1
            continue
        e = close[i]
        end = min(i + max_hold, n - 1)
        xi = end
        for j in range(i + 1, end + 1):
            if sig[j] != target:
                xi = j
                break
        xp = close[xi]
        pnl = (xp / e - 1.0) if direction == "long" else (1.0 - xp / e)
        out.append({"pnl_pct": pnl - fee_rt, "entry_bar": int(i),
                    "exit_bar": int(xi)})
        i = xi + 1                            # no overlapping positions
    return out


def funding_grid():
    """(window, thr, exit_mode) pre-registered 8-cell search grid. window is in
    funding EVENTS (8h): 30≈10d, 90≈30d. Frozen — the DSR penalty assumes this
    fixed trial count."""
    import itertools
    return list(itertools.product([30, 90], [1.0, 2.0], ["bracket", "flip"]))


def split_funding_book(frames: dict, fundings: dict, window: int, thr: float,
                       exit_mode: str, oos_start: float = 0.5):
    """Build the funding sleeve across all symbols and split each symbol's trades
    at oos_start into (in_sample, out_of_sample) by entry time. `frames` keyed by
    `{COIN}USD`; `fundings` keyed by `{COIN}`."""
    is_t, oos_t = [], []
    for sym, df in frames.items():
        coin = sym.replace("USD", "")
        funding = fundings.get(coin)
        if funding is None:
            continue
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        for t in build_funding_trades(coin, df, funding, window, thr, exit_mode):
            (oos_t if t["entry_time"] >= cut else is_t).append(t)
    return is_t, oos_t


def select_funding_sleeve(frames: dict, fundings: dict, grid=None,
                          oos_start: float = 0.5, risk_per_trade: float = 0.015,
                          max_leverage: float = 3.0, max_concurrent: int = 3) -> dict:
    """No-lookahead selection: score every grid cell by IN-SAMPLE Sharpe, pick the
    best, report its OUT-OF-SAMPLE result deflated by the grid size. Also returns
    the grid-wide Spearman IS→OOS Sharpe rank correlation (the overfit detector:
    the project's cut strategies had it negative)."""
    grid = grid or funding_grid()
    scored = []
    for window, thr, exit_mode in grid:
        is_t, oos_t = split_funding_book(frames, fundings, window, thr,
                                         exit_mode, oos_start)
        ie = portfolio_equity_sized(is_t, 500.0, risk_per_trade, max_leverage,
                                    max_concurrent, 1.0)
        oe = portfolio_equity_sized(oos_t, 500.0, risk_per_trade, max_leverage,
                                    max_concurrent, 1.0)
        scored.append({"params": (window, thr, exit_mode),
                       "is_sharpe": ie["sharpe"], "oos": oe, "oos_trades": oos_t})
    chosen = max(scored, key=lambda s: s["is_sharpe"])
    wp = chosen["oos"]["weighted_pnls"]
    dsr = deflated_sharpe_ratio(wp, num_trials=len(grid)) if wp else 0.0
    is_oos_corr = _spearman([s["is_sharpe"] for s in scored],
                            [s["oos"]["sharpe"] for s in scored])
    return {"chosen": chosen, "scored": scored, "dsr": round(dsr, 4),
            "n_grid": len(grid), "is_oos_corr": round(is_oos_corr, 4)}
