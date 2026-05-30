"""Shared edge strategy logic — the single source of truth.

Both `comprehensive_backtest.py` (offline edge discovery) and the live edge
signal feed (`app/engines/edge/signals.py`) import these functions, so the
signals that trade live are byte-identical to the ones that were validated.

Long-only, vectorized → boolean numpy array. Do NOT "improve" a signal here
without re-running the backtest — the gate thresholds in `registry.py` are
calibrated against this exact logic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def signals_ma_crossover(df: pd.DataFrame) -> np.ndarray:
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bull = fast > slow
    return (bull & ~bull.shift(1).fillna(False)).to_numpy()


def signals_mean_reversion(df: pd.DataFrame) -> np.ndarray:
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    cross_up = (rsi > 30) & (rsi.shift(1) <= 30)
    return cross_up.fillna(False).to_numpy()


def signals_breakout(df: pd.DataFrame) -> np.ndarray:
    hh = df["high"].rolling(20).max().shift(1)
    cross = df["close"] > hh
    return (cross & ~cross.shift(1).fillna(False)).fillna(False).to_numpy()


def signals_price_action(df: pd.DataFrame) -> np.ndarray:
    # Bullish engulfing
    prev_bear = df["close"].shift(1) < df["open"].shift(1)
    curr_bull = df["close"] > df["open"]
    engulf = (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
    return (prev_bear & curr_bull & engulf).fillna(False).to_numpy()


def signals_smc(df: pd.DataFrame) -> np.ndarray:
    # Bullish fair-value-gap: low of bar > high of bar two back
    gap = df["low"] - df["high"].shift(2)
    curr_bull = df["close"] > df["open"]
    return ((gap > 0) & curr_bull).fillna(False).to_numpy()


SIGNAL_FNS = {
    "ma_crossover": signals_ma_crossover,
    "mean_reversion": signals_mean_reversion,
    "breakout": signals_breakout,
    "price_action": signals_price_action,
    "smc": signals_smc,
}


def atr14(df: pd.DataFrame) -> pd.Series:
    """True-range ATR(14), matching the backtest's resample() ATR exactly."""
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(14).mean()


def resample(df_1m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 1-minute OHLCV to `rule` and recompute ATR(14) on the new bars."""
    if rule == "1min":
        return df_1m
    agg = df_1m.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["close"])
    agg["atr"] = atr14(agg)
    return agg
