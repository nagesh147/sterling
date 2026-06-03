"""Lever 1 -- symmetric SHORT-side signal generators.

Each short signal is the mirror of the corresponding long edge signal in
`app.engines.edge.strategies` (the single source of truth for the long side,
which we reuse unchanged). Vectorized -> boolean numpy array, same contract as
the long signals so the harness can take either as `long_sigs`/`short_sigs`.

`shift(..., fill_value=False)` is used on boolean cross series to keep the dtype
boolean (avoids the object-dtype `~` deprecation while preserving semantics).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.engines.edge.strategies import SIGNAL_FNS as _LONG  # reuse long defs


def short_ma_crossover(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_ma_crossover: fresh bearish EMA 9/21 cross."""
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bear = fast < slow
    return (bear & ~bear.shift(1, fill_value=False)).to_numpy()


def short_breakout(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_breakout: fresh close below the prior 20-bar low."""
    ll = df["low"].rolling(20).min().shift(1)
    cross = df["close"] < ll
    return (cross & ~cross.shift(1, fill_value=False)).to_numpy()


def short_price_action(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_price_action: bearish engulfing."""
    prev_bull = df["close"].shift(1) > df["open"].shift(1)
    curr_bear = df["close"] < df["open"]
    engulf = (df["close"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1))
    return (prev_bull & curr_bear & engulf).fillna(False).to_numpy()


def short_smc(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_smc: bearish fair-value-gap (high < low two bars back)."""
    gap = df["low"].shift(2) - df["high"]
    curr_bear = df["close"] < df["open"]
    return ((gap > 0) & curr_bear).fillna(False).to_numpy()


SHORT_FNS = {
    "ma_crossover": short_ma_crossover,
    "breakout": short_breakout,
    "price_action": short_price_action,
    "smc": short_smc,
}


def long_signal(name: str, df: pd.DataFrame) -> np.ndarray:
    return _LONG[name](df)


def short_signal(name: str, df: pd.DataFrame) -> np.ndarray:
    return SHORT_FNS[name](df)
