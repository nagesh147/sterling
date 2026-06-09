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


def route_signals(df: pd.DataFrame, adx_threshold: float = 25.0,
                  ma_window: int = 50, use_regime: bool = True):
    """Route raw sleeve signals through the regime gate.

    Returns (long_sigs, short_sigs) boolean arrays, same length as df:
      regime +1 (uptrend)   -> momentum long
      regime -1 (downtrend) -> momentum short
      regime  0 (range)     -> mean-reversion long + short

    use_regime=False is the spine baseline (no gate): momentum long+short and
    MR long+short fire everywhere — lets us measure whether the gate earns its
    degree of freedom.
    """
    reg = classify_regime(df, adx_threshold, ma_window)
    mom_long = signals_ma_crossover(df)
    mom_short = short_momentum(df)
    mr_long = signals_bb_rsi_mean_reversion(df)
    mr_short = short_mean_reversion(df)
    if not use_regime:
        longs = mom_long | mr_long
        shorts = mom_short | mr_short
        return longs, shorts
    longs = (mom_long & (reg == 1)) | (mr_long & (reg == 0))
    shorts = (mom_short & (reg == -1)) | (mr_short & (reg == 0))
    return longs, shorts


def merge_portfolio(trades: list[dict], max_concurrent: int = 3) -> list[dict]:
    """Greedy interval scheduler: accept trades in entry-time order while fewer
    than max_concurrent are open; emit the accepted set ordered by exit_time.

    Each trade is {'symbol','entry_time','exit_time','pnl_pct'}. Models a single
    book that can hold at most max_concurrent positions at once (one per name in
    the default 3-symbol case). Dropped trades are capital we did not have free.
    """
    by_entry = sorted(trades, key=lambda t: t["entry_time"])
    open_exits: list = []
    kept: list[dict] = []
    for t in by_entry:
        open_exits = [x for x in open_exits if x > t["entry_time"]]
        if len(open_exits) >= max_concurrent:
            continue
        open_exits.append(t["exit_time"])
        kept.append(t)
    return sorted(kept, key=lambda t: t["exit_time"])
