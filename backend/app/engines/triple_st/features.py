"""Indicator computation for the daily SMA/EMA + RSI/ADX strategy.

Everything the per-bar engine reads is precomputed here into aligned numpy
arrays so evaluation is O(1) per bar and the backtest can replay hundreds of
daily bars cheaply. Built on the kept `engines.indicators` library; the simple
moving average (not in that library) is computed locally.

Anti-repaint note: SMA / EMA / RSI / ADX are all causal (value at bar *i* uses
only bars ≤ *i*), and the engine reads the *closed* daily bar, so a forming bar
can never repaint a signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from numpy.typing import NDArray

from app.schemas.market import Candle
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.adx import adx as _adx
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.rsi import rsi as _rsi

from app.engines.triple_st.config import TripleSTConfig


# ─────────────────────────────────────────────────────────────────────────────
# Local indicator
# ─────────────────────────────────────────────────────────────────────────────


def rolling_sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Simple moving average. Warm-up bars (< period) carry 0.0."""
    n = len(values)
    out = np.zeros(n)
    if n < period or period < 1:
        return out
    csum = np.cumsum(values)
    out[period - 1] = csum[period - 1] / period
    out[period:] = (csum[period:] - csum[:-period]) / period
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Daily resampling (the store/adapter may serve intraday candles)
# ─────────────────────────────────────────────────────────────────────────────


def resample_to_daily(candles: List[Candle]) -> List[Candle]:
    """Aggregate intraday candles into UTC daily bars.

    open = first, high = max, low = min, close = last, volume = sum, grouped by
    UTC calendar day. Candles must be time-ascending. A bar already on a ≥1d
    cadence passes through unchanged.
    """
    if not candles:
        return []
    buckets: dict[int, List[Candle]] = {}
    order: List[int] = []
    for c in candles:
        day = int(c.timestamp_ms) // 86_400_000
        if day not in buckets:
            buckets[day] = []
            order.append(day)
        buckets[day].append(c)

    daily: List[Candle] = []
    for day in order:
        group = buckets[day]
        daily.append(Candle(
            timestamp_ms=day * 86_400_000,
            open=group[0].open,
            high=max(c.high for c in group),
            low=min(c.low for c in group),
            close=group[-1].close,
            volume=sum(c.volume for c in group),
        ))
    return daily


# ─────────────────────────────────────────────────────────────────────────────
# Feature bundle
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Features:
    """All precomputed daily arrays, index-aligned with the input candle list."""
    ts: NDArray[np.int64]
    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    close: NDArray[np.float64]
    volume: NDArray[np.float64]

    sma: NDArray[np.float64]        # SMA(sma_period)
    ema: NDArray[np.float64]        # EMA(ema_period)
    rsi: NDArray[np.float64]        # RSI(rsi_period)
    adx: NDArray[np.float64]        # ADX(adx_period)
    atr: NDArray[np.float64]        # ATR(atr_period) — for stops / sizing

    @property
    def n(self) -> int:
        return len(self.close)


def _ohlcv(candles: List[Candle]):
    o = np.array([c.open for c in candles], dtype=np.float64)
    h = np.array([c.high for c in candles], dtype=np.float64)
    l = np.array([c.low for c in candles], dtype=np.float64)
    cl = np.array([c.close for c in candles], dtype=np.float64)
    v = np.array([c.volume for c in candles], dtype=np.float64)
    ts = np.array([c.timestamp_ms for c in candles], dtype=np.int64)
    return ts, o, h, l, cl, v


def compute_features(candles: List[Candle], cfg: TripleSTConfig) -> Features:
    """Compute every indicator the strategy needs in one pass over daily bars."""
    ts, o, h, l, cl, v = _ohlcv(candles)
    return Features(
        ts=ts, open=o, high=h, low=l, close=cl, volume=v,
        sma=rolling_sma(cl, cfg.sma_period),
        ema=compute_ema(cl, cfg.ema_period),
        rsi=_rsi(cl, cfg.rsi_period),
        adx=_adx(h, l, cl, cfg.adx_period),
        atr=compute_atr(h, l, cl, cfg.atr_period),
    )
