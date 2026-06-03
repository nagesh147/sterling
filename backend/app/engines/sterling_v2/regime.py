"""Lever 2 -- interpretable conviction / regime gate (rule-based, no ML).

`build_gate(df, adx_min, side)` returns an `entry_filter(df, i)` compatible with
the harness `EntryFilter` type. The filter allows an entry at bar `i` only when:
  1. ADX (Wilder, period 14) at bar i-1 shows a real trend (>= adx_min), and
  2. the higher-timeframe EMA slope agrees with the trade side.

Both inputs use only bars <= i-1, so there is no lookahead. ADX is the Wilder
recursion from app.engines.indicators.adx -- value at bar k depends only on bars
<= k, so precomputing it on the full df is lookahead-safe (proved by
test_gate_no_lookahead).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.engines.indicators.adx import adx as _adx


def _htf_trend_up(df: pd.DataFrame, i: int, span: int = 50) -> bool:
    """EMA slope using only bars <= i-1 (no lookahead)."""
    if i < span + 2:
        return False
    ema = df["close"].iloc[:i].ewm(span=span, adjust=False).mean()
    return bool(ema.iloc[-1] > ema.iloc[-2])


def build_gate(df: pd.DataFrame, adx_min: float = 18.0, side: int = 1):
    """Return an entry_filter(df, i) using only bars <= i-1. Interpretable, no
    ML dependency: trade only when ADX confirms a trend AND the higher-TF EMA
    slope agrees with the side (+1 long / -1 short)."""
    adx_arr = np.asarray(
        _adx(df["high"].to_numpy(float), df["low"].to_numpy(float),
             df["close"].to_numpy(float), period=14),
        float,
    )

    def _filter(_df: pd.DataFrame, i: int) -> bool:
        if i <= 0 or i - 1 >= len(adx_arr):
            return False
        a = adx_arr[i - 1]
        if not np.isfinite(a) or a < adx_min:
            return False
        up = _htf_trend_up(_df, i)
        return up if side == 1 else (not up)

    return _filter
