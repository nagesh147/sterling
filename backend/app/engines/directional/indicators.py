"""Real technical indicators for the directional signal/regime engines.

Standard Wilder-smoothed ADX/RSI + SMA helpers, computed on a candle DataFrame.
These replace the fabricated stubs (`adx = 10 + int(close) % 30`, `score = 85`)
so the live signals reflect genuine analysis. Pure functions — no I/O, no state.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

from app.schemas.market import Candle

_WILDER = 1 / 14.0


def candles_to_df(candles: List[Candle]) -> pd.DataFrame:
    """Candle objects → OHLCV DataFrame (chronological)."""
    return pd.DataFrame({
        "open": [float(c.open) for c in candles],
        "high": [float(c.high) for c in candles],
        "low": [float(c.low) for c in candles],
        "close": [float(c.close) for c in candles],
        "volume": [float(c.volume) for c in candles],
    })


def rsi14(close: pd.Series) -> pd.Series:
    """Wilder RSI(14)."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=_WILDER, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=_WILDER, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def adx14(df: pd.DataFrame) -> pd.Series:
    """Wilder ADX(14) — trend strength (0-100). Higher = stronger directional trend."""
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=_WILDER, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=_WILDER, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=_WILDER, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=_WILDER, adjust=False).mean().fillna(0.0)


def sma_slope(close: pd.Series, window: int = 50, lookback: int = 5) -> float:
    """Sign-carrying slope of SMA(window) over the last `lookback` bars, as a
    fraction of price. Positive = rising trend, negative = falling."""
    sma = close.rolling(window).mean()
    if sma.notna().sum() <= lookback or close.iloc[-1] <= 0:
        return 0.0
    return float((sma.iloc[-1] - sma.iloc[-1 - lookback]) / close.iloc[-1])
