"""
Hybrid VCP-Momentum Scalper — Strategy V2
All OHLCV-based technical indicators. Pure functions, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class VCPConfig:
    bb_period: int = 20
    bb_std: float = 2.0
    bb_width_pct_lookback: int = 60
    compression_threshold_pct: float = 30.0


@dataclass(frozen=True)
class MomentumConfig:
    rsi_period: int = 14
    ema_fast: int = 8
    ema_slow: int = 21
    pivot_lookback: int = 6
    volume_ma_period: int = 20
    volume_spike_mult: float = 1.25
    rsi_breakout_long: float = 52.0
    rsi_breakout_short: float = 48.0


@dataclass(frozen=True)
class ATRConfig:
    period: int = 14
    atr_pct_lookback: int = 50
    vol_filter_threshold: float = 35.0


# ──────────────────────────────────────────────────────────────────────────────
# ATR
# ──────────────────────────────────────────────────────────────────────────────

def compute_atr(
    highs: NDArray[np.float64],
    lows:  NDArray[np.float64],
    closes: NDArray[np.float64],
    period: int = 14,
) -> NDArray[np.float64]:
    """Wilder's ATR (RMA smoothing)."""
    n = len(closes)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1]),
        )
    atr = np.zeros(n)
    if n <= period:
        return atr
    atr[period] = float(np.mean(tr[1:period + 1]))
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def atr_percentile(atr: NDArray[np.float64], lookback: int = 50) -> float:
    """Current ATR as percentile rank vs trailing lookback bars. Returns 0-100."""
    if atr.size < 5 or np.isnan(atr[-1]):
        return 50.0
    valid = atr[-lookback:][~np.isnan(atr[-lookback:])]
    if valid.size < 5:
        return 50.0
    return float(np.sum(atr[-1] > valid) / valid.size * 100.0)


# ──────────────────────────────────────────────────────────────────────────────
# Bollinger Bands
# ──────────────────────────────────────────────────────────────────────────────

def compute_bb(
    closes: NDArray[np.float64],
    period: int = 20,
    std_mult: float = 2.0,
) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Returns (bb_upper, bb_mid, bb_lower)."""
    mid = np.convolve(closes, np.ones(period) / period, mode="valid")
    n_valid = len(mid)
    if n_valid == 0:
        return np.zeros_like(closes), np.zeros_like(closes), np.zeros_like(closes)

    upper = np.zeros(n_valid)
    lower = np.zeros(n_valid)
    for i in range(n_valid):
        window = closes[i - period + 1:i + 1]
        if len(window) == period:
            std = float(np.std(window, ddof=0))
            upper[i] = mid[i] + std_mult * std
            lower[i] = mid[i] - std_mult * std

    # Pad back to original length
    pad = len(closes) - n_valid
    bb_upper = np.concatenate([np.zeros(pad) + closes[0], upper])
    bb_mid   = np.concatenate([np.zeros(pad) + closes[0], mid])
    bb_lower = np.concatenate([np.zeros(pad) + closes[0], lower])
    return bb_upper, bb_mid, bb_lower


def bb_width_percentile(
    closes: NDArray[np.float64],
    lookback: int = 60,
    period: int = 20,
    std_mult: float = 2.0,
) -> float:
    """
    Bollinger width as a percentile rank.
    Returns 0-100. Low values (< 30) = compression (VCP setup).
    """
    bb_upper, bb_mid, bb_lower = compute_bb(closes, period, std_mult)
    widths = (bb_upper - bb_lower) / np.maximum(bb_mid, 1e-9)
    recent = widths[-lookback:]
    valid = recent[~np.isnan(recent)]
    if valid.size < 10:
        return 50.0
    cur = widths[-1] if not np.isnan(widths[-1]) else float(np.nanmean(valid))
    return float(np.sum(cur < valid) / valid.size * 100.0)


# ──────────────────────────────────────────────────────────────────────────────
# RSI
# ──────────────────────────────────────────────────────────────────────────────

def compute_rsi(closes: NDArray[np.float64], period: int = 14) -> NDArray[np.float64]:
    """Standard RSI(14)."""
    n = len(closes)
    rsi = np.zeros(n)
    if n <= period:
        return rsi

    deltas = np.diff(closes, axis=0)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    if avg_loss == 0:
        rsi[period:] = 100.0
        return rsi

    rs = avg_gain / avg_loss
    rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


# ──────────────────────────────────────────────────────────────────────────────
# EMA
# ──────────────────────────────────────────────────────────────────────────────

def compute_ema(closes: NDArray[np.float64], span: int) -> NDArray[np.float64]:
    """Exponential moving average."""
    alpha = 2.0 / (span + 1)
    ema = np.zeros_like(closes)
    ema[0] = closes[0]
    for i in range(1, len(closes)):
        ema[i] = alpha * closes[i] + (1 - alpha) * ema[i - 1]
    return ema


# ──────────────────────────────────────────────────────────────────────────────
# Volume
# ──────────────────────────────────────────────────────────────────────────────

def compute_vol_sma(volume: NDArray[np.float64], period: int = 20) -> NDArray[np.float64]:
    """Simple moving average of volume."""
    sma = np.zeros_like(volume, dtype=np.float64)
    for i in range(period - 1, len(volume)):
        sma[i] = float(np.mean(volume[i - period + 1:i + 1]))
    return sma


# ──────────────────────────────────────────────────────────────────────────────
# IBS — Internal Bar Strength
# ──────────────────────────────────────────────────────────────────────────────

def compute_ibs(
    highs: NDArray[np.float64],
    lows:  NDArray[np.float64],
    closes: NDArray[np.float64],
) -> NDArray[np.float64]:
    """IBS = (close - low) / (high - low). Range [0, 1]."""
    range_ = highs - lows
    range_ = np.where(range_ == 0, 1e-9, range_)
    return (closes - lows) / range_


# ──────────────────────────────────────────────────────────────────────────────
# Pivot High / Low
# ──────────────────────────────────────────────────────────────────────────────

def compute_pivot_high(
    highs: NDArray[np.float64],
    lookback: int = 6,
) -> NDArray[np.float64]:
    """Rolling pivot high over lookback window."""
    n = len(highs)
    pivots = np.zeros(n)
    for i in range(lookback - 1, n):
        pivots[i] = float(np.max(highs[i - lookback + 1:i + 1]))
    return pivots


def compute_pivot_low(
    lows: NDArray[np.float64],
    lookback: int = 6,
) -> NDArray[np.float64]:
    """Rolling pivot low over lookback window."""
    n = len(lows)
    pivots = np.zeros(n)
    for i in range(lookback - 1, n):
        pivots[i] = float(np.min(lows[i - lookback + 1:i + 1]))
    return pivots


# ──────────────────────────────────────────────────────────────────────────────
# All-in-one indicator bundle — used by backtest vectoriser
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IndicatorBundle:
    atr:        NDArray[np.float64]
    rsi:        NDArray[np.float64]
    ema8:       NDArray[np.float64]
    ema21:      NDArray[np.float64]
    bb_upper:   NDArray[np.float64]
    bb_mid:     NDArray[np.float64]
    bb_lower:   NDArray[np.float64]
    vol_sma20:  NDArray[np.float64]
    ibs:        NDArray[np.float64]
    pivot_high: NDArray[np.float64]
    pivot_low:  NDArray[np.float64]


def compute_bundle(
    opens:   NDArray[np.float64],
    highs:   NDArray[np.float64],
    lows:    NDArray[np.float64],
    closes:  NDArray[np.float64],
    volume:  NDArray[np.float64],
    *,
    atr_period:      int = 14,
    bb_period:        int = 20,
    bb_std:           float = 2.0,
    rsi_period:       int = 14,
    ema_fast:         int = 8,
    ema_slow:         int = 21,
    vol_ma_period:    int = 20,
    pivot_lookback:   int = 6,
) -> IndicatorBundle:
    """Compute all indicators in one pass."""
    atr       = compute_atr(highs, lows, closes, atr_period)
    rsi       = compute_rsi(closes, rsi_period)
    ema8      = compute_ema(closes, ema_fast)
    ema21     = compute_ema(closes, ema_slow)
    bb_upper, bb_mid, bb_lower = compute_bb(closes, bb_period, bb_std)
    vol_sma20 = compute_vol_sma(volume, vol_ma_period)
    ibs       = compute_ibs(highs, lows, closes)
    pivot_high = compute_pivot_high(highs, pivot_lookback)
    pivot_low  = compute_pivot_low(lows, pivot_lookback)
    return IndicatorBundle(
        atr=atr, rsi=rsi, ema8=ema8, ema21=ema21,
        bb_upper=bb_upper, bb_mid=bb_mid, bb_lower=bb_lower,
        vol_sma20=vol_sma20, ibs=ibs,
        pivot_high=pivot_high, pivot_low=pivot_low,
    )