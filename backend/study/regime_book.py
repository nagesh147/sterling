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


# (sl, tp) bracket used for both directions; Aggressive profile from the study.
_SL, _TP = 1.5, 4.5


def build_symbol_trades(symbol: str, df: pd.DataFrame, adx_threshold: float = 25.0,
                        ma_window: int = 50, use_regime: bool = True,
                        trail_mult: float | None = None) -> list[dict]:
    """Route, simulate long+short, return trades tagged with symbol + timestamps."""
    longs, shorts = route_signals(df, adx_threshold, ma_window, use_regime)
    out: list[dict] = []
    for sigs, direction in ((longs, "long"), (shorts, "short")):
        raw = simulate_idx(df, sigs, _SL, _TP, direction=direction,
                           fee_rt=FEE_RT, max_hold=MAX_HOLD, trail_mult=trail_mult)
        for t in raw:
            out.append({
                "symbol": symbol,
                "direction": direction,
                "entry_time": df.index[t["entry_bar"]],
                "exit_time": df.index[t["exit_bar"]],
                "pnl_pct": t["pnl_pct"],
            })
    return out


def portfolio_equity(trades: list[dict], cap: float = 500.0,
                     max_concurrent: int = 3) -> dict:
    """Cap concurrency, then compound a single book where each trade risks a
    1/max_concurrent slice of equity (equal-risk allocation). Exit-time ordered."""
    kept = merge_portfolio(trades, max_concurrent)
    w = 1.0 / max_concurrent
    pnls = [t["pnl_pct"] for t in kept]
    if not pnls:
        return {"end": cap, "ret": 0.0, "sharpe": 0.0, "max_dd": 0.0,
                "n": 0, "weighted_pnls": []}
    wpnls = [p * w for p in pnls]
    a = np.asarray(wpnls, float)
    eq = cap * np.cumprod(1 + a)
    peak = np.maximum.accumulate(eq)
    return {"end": float(eq[-1]), "ret": float(eq[-1] / cap - 1.0),
            "sharpe": _sharpe(wpnls), "max_dd": float(((eq - peak) / peak).min()),
            "n": len(pnls), "weighted_pnls": wpnls}


def walk_forward_book(frames: dict, adx_threshold: float = 25.0,
                      ma_window: int = 50, use_regime: bool = True,
                      trail_mult: float | None = None, n_folds: int = 5,
                      oos_start: float = 0.5, cap: float = 500.0,
                      max_concurrent: int = 3) -> dict:
    """Pool all symbols, take the OOS tail [oos_start, 1.0] of calendar time as
    the forward book. The regime/short/MR logic uses only past bars per signal,
    so a fixed-parameter forward evaluation is leak-free. (Parameter SELECTION
    across adx_threshold is done by the caller comparing whole-book OOS results,
    never per-fold on test data.) Returns OOS book stats + DSR + hold-beat."""
    all_trades: list[dict] = []
    hodl_prices: list[float] = []
    for sym, df in frames.items():
        t0, t1 = df.index[0], df.index[-1]
        cut = t0 + (t1 - t0) * oos_start
        trades = build_symbol_trades(sym, df, adx_threshold, ma_window,
                                     use_regime, trail_mult)
        all_trades += [t for t in trades if t["entry_time"] >= cut]
        sub = df["close"][df.index >= cut]
        if len(sub) > 1:
            hodl_prices += list(sub.to_numpy())
    eq = portfolio_equity(all_trades, cap, max_concurrent)
    hodl = hodl_benchmark(hodl_prices, fee_rt_pct=FEE_RT)
    rel = beats_buy_and_hold(eq["ret"], eq["max_dd"], hodl)
    dsr = deflated_sharpe_ratio(eq["weighted_pnls"], num_trials=525) \
        if eq["weighted_pnls"] else 0.0
    return {"oos": eq, "dsr": round(dsr, 4),
            "beats_hold": rel["beats_hold"], "excess_vs_hold": rel["excess_return"],
            "n": eq["n"], "hodl": hodl}
