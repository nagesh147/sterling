from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np
import pandas as pd
from .config import SimConfig

# Entry filter: (df, i) -> bool (allow entry at bar i). Uses only bars <= i-1.
EntryFilter = Callable[[pd.DataFrame, int], bool]


@dataclass
class SimResult:
    returns: np.ndarray            # per-trade fractional returns (after costs)
    entry_times: list             # entry timestamps
    bars_held: list
    sides: list                   # +1 long, -1 short
    df_index: pd.DatetimeIndex


def simulate(df: pd.DataFrame,
             long_sigs: np.ndarray,
             short_sigs: Optional[np.ndarray],
             cfg: SimConfig,
             entry_filter: Optional[EntryFilter] = None) -> SimResult:
    """Sequential, non-overlapping. Entry fills at NEXT bar open (+/- slippage).
    First-touch SL/TP with slippage on stops; funding drag per bar held.
    Short side mirrored when cfg.allow_short and short_sigs provided."""
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float);  c = df["close"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    idx = df.index
    n = len(c)
    short_sigs = short_sigs if short_sigs is not None else np.zeros(n, bool)

    rets: list[float] = []; etimes = []; held = []; sides = []
    pos = 0; ein = -1; entry = sl = tp = 0.0; side = 0
    fee = cfg.fee_round_trip; slip = cfg.slippage; fund = cfg.funding_per_bar
    i = 0
    while i < n:
        if pos == 0:
            # Need a next bar to fill entry; skip the last bar for new entries
            if i >= n - 1:
                i += 1; continue
            go_long = bool(long_sigs[i]) and np.isfinite(atr[i]) and atr[i] > 0
            go_short = (cfg.allow_short and bool(short_sigs[i])
                        and np.isfinite(atr[i]) and atr[i] > 0)
            if (go_long or go_short) and (entry_filter is None or entry_filter(df, i)):
                side = 1 if go_long else -1
                if side == 1:
                    entry = o[i + 1] * (1 + slip)
                    sl = entry - cfg.sl_mult * atr[i]; tp = entry + cfg.tp_mult * atr[i]
                else:
                    entry = o[i + 1] * (1 - slip)
                    sl = entry + cfg.sl_mult * atr[i]; tp = entry - cfg.tp_mult * atr[i]
                pos = side; ein = i + 1; i += 1; continue
            i += 1; continue
        # in position
        exit_px = None
        if pos == 1:
            if l[i] <= sl: exit_px = sl * (1 - slip)
            elif h[i] >= tp: exit_px = tp
        else:  # short
            if h[i] >= sl: exit_px = sl * (1 + slip)
            elif l[i] <= tp: exit_px = tp
        if exit_px is None and (i - ein) >= cfg.max_hold_bars:
            exit_px = c[i]
        if exit_px is not None:
            gross = (exit_px / entry - 1.0) * pos
            bh = i - ein
            rets.append(gross - fee - fund * bh)
            etimes.append(idx[ein]); held.append(bh); sides.append(pos)
            pos = 0
        i += 1
    return SimResult(np.array(rets, float), etimes, held, sides, idx)


def compute_metrics(res: SimResult, weights: Optional[np.ndarray] = None) -> dict:
    """Win/PF/Sharpe(net)/maxDD/net. Sharpe annualized by REALIZED trade
    frequency (trades per year from actual timestamps), not a constant."""
    r = res.returns
    if weights is not None:
        r = r * weights
    n = r.size
    if n == 0:
        return dict(trades=0, win=0.0, pf=0.0, sharpe=0.0, net=0.0,
                    max_dd=0.0, expectancy=0.0, trades_per_year=0.0)
    wins = r[r > 0]; losses = r[r < 0]
    gp = float(wins.sum()); gl = float(-losses.sum())
    pf = gp / gl if gl > 0 else float("inf")
    eq = np.cumprod(1 + r); peak = np.maximum.accumulate(eq)
    max_dd = float(((eq - peak) / peak).min())
    if len(res.entry_times) >= 2:
        span_days = (res.entry_times[-1] - res.entry_times[0]).days or 1
        tpy = n / (span_days / 365.25)
    else:
        tpy = 0.0
    sd = r.std(ddof=1) if n >= 2 else 0.0
    sharpe = float(r.mean() / sd * np.sqrt(tpy)) if sd > 1e-12 and tpy > 0 else 0.0
    win = wins.size / n
    exp = win * (wins.mean() if wins.size else 0.0) - (1 - win) * (-losses.mean() if losses.size else 0.0)
    return dict(trades=n, win=win, pf=pf, sharpe=sharpe, net=float(eq[-1] - 1.0),
                max_dd=max_dd, expectancy=float(exp), trades_per_year=float(tpy))
