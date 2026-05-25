"""One-shot indicator computation for the Triple SuperTrend strategy.

Everything the per-bar engine reads is precomputed here into aligned numpy
arrays so evaluation is O(1) per bar and the backtest can replay thousands of
bars cheaply. Built on the kept `engines.indicators` library; MACD histogram
and the Choppiness Index (not in that library) are computed locally.

Anti-repaint note: SuperTrend / ADX / ATR are all causal (value at bar *i*
uses only bars ≤ *i*). The engine still reads confirmation values at `[i-1]`
where a *flip* must be confirmed, so a forming bar can never repaint a signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from app.schemas.market import Candle
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.adx import adx as _adx
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.rsi import rsi as _rsi
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend

from app.engines.triple_st.config import ST_CONFIGS


# ─────────────────────────────────────────────────────────────────────────────
# Local indicators (not in the shared library)
# ─────────────────────────────────────────────────────────────────────────────


def macd_histogram(
    close: NDArray[np.float64], fast: int = 12, slow: int = 26, signal: int = 9
) -> NDArray[np.float64]:
    """MACD histogram = (EMA_fast − EMA_slow) − EMA_signal(MACD line)."""
    macd_line = compute_ema(close, fast) - compute_ema(close, slow)
    signal_line = compute_ema(macd_line, signal)
    return macd_line - signal_line


def choppiness_index(
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    close: NDArray[np.float64],
    period: int = 14,
) -> NDArray[np.float64]:
    """Choppiness Index (0-100). >61.8 = choppy/ranging, <38.2 = trending."""
    n = len(close)
    chop = np.full(n, 50.0)
    if n <= period:
        return chop
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    log_p = np.log10(period)
    for i in range(period, n):
        atr_sum = float(np.sum(tr[i - period + 1 : i + 1]))
        hh = float(np.max(high[i - period + 1 : i + 1]))
        ll = float(np.min(low[i - period + 1 : i + 1]))
        rng = hh - ll
        if rng > 0 and atr_sum > 0:
            chop[i] = 100.0 * np.log10(atr_sum / rng) / log_p
    return np.clip(chop, 0.0, 100.0)


def rolling_sma(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    n = len(values)
    out = np.zeros(n)
    if n < period:
        return out
    csum = np.cumsum(values)
    out[period - 1] = csum[period - 1] / period
    out[period:] = (csum[period:] - csum[:-period]) / period
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Primary-timeframe feature bundle
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Features:
    """All precomputed arrays for the primary (signal) timeframe.

    Arrays are index-aligned with the input candle list. Zero-volume bars are
    handled gracefully (volume_ratio falls back to 1.0 when the MA is 0).
    """
    ts: NDArray[np.int64]
    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    close: NDArray[np.float64]
    volume: NDArray[np.float64]

    atr14: NDArray[np.float64]
    atr50: NDArray[np.float64]
    adx: NDArray[np.float64]
    ema20: NDArray[np.float64]
    ema50: NDArray[np.float64]
    ema100: NDArray[np.float64]
    rsi: NDArray[np.float64]
    macd_hist: NDArray[np.float64]
    chop: NDArray[np.float64]
    bb_width: NDArray[np.float64]
    bb_width_sma50: NDArray[np.float64]
    vol_ma: NDArray[np.float64]
    vol_ratio: NDArray[np.float64]
    ha_bull: NDArray[np.bool_]
    ha_body: NDArray[np.float64]        # |HA close − HA open|

    # Triple SuperTrend: lines + trends, one per ST_CONFIGS entry.
    st_lines: List[NDArray[np.float64]] = field(default_factory=list)
    st_trends: List[NDArray[np.int64]] = field(default_factory=list)

    atr_percent: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))

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


def compute_features(candles: List[Candle], vol_ma_period: int = 20) -> Features:
    """Compute every primary-timeframe indicator in one pass."""
    ts, o, h, l, cl, v = _ohlcv(candles)
    n = len(cl)

    atr14 = compute_atr(h, l, cl, 14)
    atr50 = compute_atr(h, l, cl, 50)
    adx_arr = _adx(h, l, cl, 14)
    ema20 = compute_ema(cl, 20)
    ema50 = compute_ema(cl, 50)
    ema100 = compute_ema(cl, 100)
    rsi_arr = _rsi(cl, 14)
    macd_h = macd_histogram(cl)
    chop = choppiness_index(h, l, cl, 14)

    lower, mid, upper = bollinger_bands(cl, 20, 2.0)
    bb_width = np.zeros(n)
    nz = mid > 0
    bb_width[nz] = (upper[nz] - lower[nz]) / mid[nz]
    bb_width_sma50 = rolling_sma(bb_width, 50)

    vol_ma = rolling_sma(v, max(2, vol_ma_period))
    vol_ratio = np.ones(n)
    nzv = vol_ma > 0
    vol_ratio[nzv] = v[nzv] / vol_ma[nzv]

    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, cl)
    ha_bull = ha_c > ha_o
    ha_body = np.abs(ha_c - ha_o)

    # Triple SuperTrend is computed on Heikin-Ashi candles (non-repainting) to
    # match how the TradingView reference chart renders it — TV computes the
    # SuperTrend on whatever candle type the chart shows, and the strategy chart
    # is HA. Raw-OHLC SuperTrend flips faster and disagrees with the chart.
    st_lines, st_trends = [], []
    for period, mult in ST_CONFIGS:
        line, trend = compute_supertrend(ha_h, ha_l, ha_c, period, mult)
        st_lines.append(line)
        st_trends.append(trend)

    atr_percent = np.zeros(n)
    nzc = cl > 0
    atr_percent[nzc] = atr14[nzc] / cl[nzc] * 100.0

    return Features(
        ts=ts, open=o, high=h, low=l, close=cl, volume=v,
        atr14=atr14, atr50=atr50, adx=adx_arr,
        ema20=ema20, ema50=ema50, ema100=ema100,
        rsi=rsi_arr, macd_hist=macd_h, chop=chop,
        bb_width=bb_width, bb_width_sma50=bb_width_sma50,
        vol_ma=vol_ma, vol_ratio=vol_ratio,
        ha_bull=ha_bull, ha_body=ha_body,
        st_lines=st_lines, st_trends=st_trends,
        atr_percent=atr_percent,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Higher-timeframe + BTC context (timestamp-aligned look-ups)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class HTFContext:
    """Higher-timeframe (e.g. 4H) bias, looked up by primary-bar timestamp.

    `bias_at` returns the last *closed* HTF bar's bias, so a 1H bar inside a
    forming 4H candle reads the previously-closed 4H bias (anti-repaint).
    """
    ts: NDArray[np.int64]
    st_trend: NDArray[np.int64]      # HTF supertrend trend (+1/-1)
    ema_trend: NDArray[np.int64]     # sign(close − ema50)

    @classmethod
    def build(cls, candles: List[Candle]) -> Optional["HTFContext"]:
        if len(candles) < 60:
            return None
        ts, o, h, l, cl, _v = _ohlcv(candles)
        ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, cl)
        _line, st_trend = compute_supertrend(ha_h, ha_l, ha_c, 10, 3.0)  # HA, matches chart
        ema50 = compute_ema(cl, 50)
        ema_trend = np.sign(cl - ema50).astype(np.int64)
        return cls(ts=ts, st_trend=st_trend, ema_trend=ema_trend)

    def _idx(self, ts_ms: int) -> int:
        # last HTF bar whose open-time is ≤ the primary bar's timestamp
        i = int(np.searchsorted(self.ts, ts_ms, side="right")) - 1
        return max(0, min(i, len(self.ts) - 1))

    def st_bias(self, ts_ms: int) -> int:
        return int(self.st_trend[self._idx(ts_ms)])

    def ema_bias(self, ts_ms: int) -> int:
        return int(self.ema_trend[self._idx(ts_ms)])


@dataclass
class BTCContext:
    """BTC trend + rolling correlation, looked up by primary-bar timestamp."""
    ts: NDArray[np.int64]
    trend: NDArray[np.int64]         # BTC 1H supertrend trend
    close: NDArray[np.float64]

    @classmethod
    def build(cls, candles: List[Candle]) -> Optional["BTCContext"]:
        if len(candles) < 60:
            return None
        ts, o, h, l, cl, _v = _ohlcv(candles)
        ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, cl)
        _line, trend = compute_supertrend(ha_h, ha_l, ha_c, 10, 3.0)  # HA, matches chart
        return cls(ts=ts, trend=trend, close=cl)

    def _idx(self, ts_ms: int) -> int:
        i = int(np.searchsorted(self.ts, ts_ms, side="right")) - 1
        return max(0, min(i, len(self.ts) - 1))

    def trend_at(self, ts_ms: int) -> int:
        return int(self.trend[self._idx(ts_ms)])

    def daily_move_pct(self, ts_ms: int) -> float:
        """Approx 24-bar (≈1 day on 1H) BTC % move ending at this timestamp."""
        i = self._idx(ts_ms)
        j = max(0, i - 24)
        if self.close[j] <= 0:
            return 0.0
        return (self.close[i] - self.close[j]) / self.close[j] * 100.0
