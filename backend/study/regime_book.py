"""Regime-gated, symmetric (long+short), 3-symbol-pooled research book.

RESEARCH TOOL — not wired into anything live. Answers one honest question:
does routing momentum vs mean-reversion by regime, allowing shorts, and pooling
BTC/ETH/SOL into one capped book produce a FORWARD edge that beats the long-only
single-symbol baseline — and does anything clear DSR >= 0.5?

Spec: docs/superpowers/specs/2026-06-09-regime-book-rework-design.md
Run:  cd backend && .venv/bin/python -m study.regime_book
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

from app.engines.edge.strategies import (
    resample, signals_ma_crossover, signals_bb_rsi_mean_reversion,
)
from study.sim import simulate_idx, sharpe as _sharpe
from app.engines.edge.robustness import deflated_sharpe_ratio
from app.engines.analytics.performance import hodl_benchmark, beats_buy_and_hold

FEE_RT = 0.001
MAX_HOLD = 200


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ADX(period). Rolling/ewm only → leak-free."""
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def classify_regime(df: pd.DataFrame, adx_threshold: float = 25.0,
                    ma_window: int = 50) -> np.ndarray:
    """Per-bar regime: +1 uptrend, -1 downtrend, 0 range. Leak-free.

    Trend when ADX(14) >= adx_threshold; sign from the slope of SMA(ma_window).
    The single regime knob is adx_threshold; ma_window is fixed.
    """
    adx = _adx(df)
    ma = df["close"].rolling(ma_window).mean()
    slope = ma.diff()
    trend = (adx >= adx_threshold).to_numpy()
    up = (slope > 0).to_numpy()
    reg = np.zeros(len(df), dtype=int)
    reg[trend & up] = 1
    reg[trend & ~up] = -1
    reg[~np.isfinite(adx.to_numpy())] = 0
    return reg


def short_momentum(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_ma_crossover: fire on a fresh bearish 9/21 EMA cross."""
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bear = fast < slow
    return (bear & ~bear.shift(1).fillna(False)).to_numpy()


def short_mean_reversion(df: pd.DataFrame) -> np.ndarray:
    """Mirror of signals_bb_rsi_mean_reversion: fade the upper Bollinger band
    (close drops back below upper) while RSI(14) is hot (> 60)."""
    c = df["close"]
    d = c.diff()
    gain = d.clip(lower=0).rolling(14).mean()
    loss = (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sma = c.rolling(20).mean()
    std = c.rolling(20).std()
    upper = sma + 2 * std
    fade = (c < upper) & (c.shift(1) >= upper.shift(1))
    return (fade & (rsi > 60)).fillna(False).to_numpy()
