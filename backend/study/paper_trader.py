"""Paper trader for the validated conviction book — REAL DATA, ISOLATED.

Runs the exact validated conviction regime book (adx=20, RSI<25/>65, vol-target
sizing, sleeve-specific exits) on real Binance bars and keeps a persisted paper
account, so a genuine forward (out-of-sample-in-calendar-time) track record
accumulates run by run. It deliberately does NOT touch the live SterlingEngine:
the book is not deflation-provable (DSR 0.166 < 0.5), so it earns trust by
paper-trading, not by going live.

Design invariant: realized equity over [inception, now] is computed with the
SAME `portfolio_equity_sized` the backtest used, so the paper book can never
drift from what was validated. `walk_positions` only adds the live concept the
backtest lacks — a position that is still OPEN at the latest bar.

Spec/report: docs/regime_book_before_after.md.
Run:  cd backend && .venv/bin/python -m study.paper_trader
"""
from __future__ import annotations

import numpy as np


def walk_positions(df, sigs, slm, tpm, direction="long", trail_mult=None,
                   max_hold=200, fee_rt=0.001):
    """Live first-touch SL/TP/trail walker. Like `study.sim.simulate_idx` but
    reports the position that is still OPEN at the last available bar instead of
    force-closing it.

    Returns (closed, open_pos):
      closed   — list of {pnl_pct, entry_bar, exit_bar, status} where status is
                 'sl' | 'tp' | 'time' (max_hold elapsed)
      open_pos — None, or a single {entry_bar, entry_price, sl, tp, trail,
                 unrealized_pnl, status='open'} (sequential book → ≤1 open)
    """
    close = df["close"].to_numpy(float)
    high = df["high"].to_numpy(float)
    low = df["low"].to_numpy(float)
    atr = df["atr"].to_numpy(float)
    n = len(close)

    closed: list[dict] = []
    open_pos = None
    idx = np.flatnonzero(sigs)
    sp = 0
    while sp < len(idx):
        i = int(idx[sp])
        sp += 1
        if i >= n - 1 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue

        e = close[i]
        if direction == "short":
            sl = e + slm * atr[i]
            tp = e - tpm * atr[i]
        else:
            sl = e - slm * atr[i]
            tp = e + tpm * atr[i]

        end = min(i + max_hold, n - 1)
        trail = sl if trail_mult is not None else None
        xp = xi = None
        status = None
        for j in range(i + 1, end + 1):
            if direction == "short":
                stop = trail if trail is not None else sl
                if high[j] >= stop:
                    xp, xi, status = stop, j, "sl"; break
                if low[j] <= tp:
                    xp, xi, status = tp, j, "tp"; break
                if trail is not None:
                    trail = min(trail, low[j] + trail_mult * atr[i])
            else:
                stop = trail if trail is not None else sl
                if low[j] <= stop:
                    xp, xi, status = stop, j, "sl"; break
                if high[j] >= tp:
                    xp, xi, status = tp, j, "tp"; break
                if trail is not None:
                    trail = max(trail, high[j] - trail_mult * atr[i])

        if status is not None:                       # SL or TP hit → closed
            pnl = (xp / e - 1.0 - fee_rt) if direction == "long" \
                else (1.0 - xp / e - fee_rt)
            closed.append({"pnl_pct": pnl, "entry_bar": i, "exit_bar": xi,
                           "status": status})
            while sp < len(idx) and idx[sp] <= xi:
                sp += 1
            continue

        # No SL/TP touch within available bars.
        if (end - i) >= max_hold:                    # max_hold elapsed → time exit
            xp = close[end]
            pnl = (xp / e - 1.0 - fee_rt) if direction == "long" \
                else (1.0 - xp / e - fee_rt)
            closed.append({"pnl_pct": pnl, "entry_bar": i, "exit_bar": end,
                           "status": "time"})
            while sp < len(idx) and idx[sp] <= end:
                sp += 1
            continue

        # Still open at the last bar → mark to market (sequential book stops here).
        mtm = close[n - 1]
        unreal = (mtm / e - 1.0 - fee_rt) if direction == "long" \
            else (1.0 - mtm / e - fee_rt)
        open_pos = {"entry_bar": i, "entry_price": e, "sl": sl, "tp": tp,
                    "trail": trail, "unrealized_pnl": float(unreal),
                    "status": "open"}
        break

    return closed, open_pos
