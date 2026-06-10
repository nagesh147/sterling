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
