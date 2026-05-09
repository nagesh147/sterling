import warnings
import numpy as np
from numpy.typing import NDArray
from typing import List, Optional
from app.schemas.market import Candle


def adx(
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    close: NDArray[np.float64],
    period: int = 14,
) -> NDArray[np.float64]:
    """Standard Wilder ADX. Vectorised, numpy-only. Returns ndarray aligned with close."""
    n = len(close)
    result = np.zeros(n)
    if n < period * 2 + 1:
        return result

    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        h_diff = high[i] - high[i - 1]
        l_diff = low[i - 1] - low[i]
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
        plus_dm[i] = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
        minus_dm[i] = l_diff if l_diff > h_diff and l_diff > 0 else 0.0

    atr14 = np.zeros(n)
    pdm14 = np.zeros(n)
    mdm14 = np.zeros(n)
    atr14[period] = float(np.sum(tr[1:period + 1]))
    pdm14[period] = float(np.sum(plus_dm[1:period + 1]))
    mdm14[period] = float(np.sum(minus_dm[1:period + 1]))
    for i in range(period + 1, n):
        atr14[i] = atr14[i - 1] - atr14[i - 1] / period + tr[i]
        pdm14[i] = pdm14[i - 1] - pdm14[i - 1] / period + plus_dm[i]
        mdm14[i] = mdm14[i - 1] - mdm14[i - 1] / period + minus_dm[i]

    with np.errstate(invalid="ignore", divide="ignore"):
        di_plus = np.where(atr14 > 0, 100.0 * pdm14 / atr14, 0.0)
        di_minus = np.where(atr14 > 0, 100.0 * mdm14 / atr14, 0.0)
        di_sum = di_plus + di_minus
        dx = np.where(di_sum > 0, 100.0 * np.abs(di_plus - di_minus) / di_sum, 0.0)

    start = period * 2
    if start >= n:
        return result
    result[start] = float(np.mean(dx[period:period * 2 + 1]))
    for i in range(start + 1, n):
        result[i] = (result[i - 1] * (period - 1) + dx[i]) / period

    return result


def calc_adx(candles: List[Candle], period: int = 14) -> List[Optional[float]]:
    """
    Wilder ADX. Returns list same length as candles.
    First (period*2) values are None.
    """
    n = len(candles)
    result: List[Optional[float]] = [None] * n
    if n < period * 2 + 1:
        return result

    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    closes = np.array([c.close for c in candles], dtype=np.float64)

    # True Range
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        h_diff = highs[i] - highs[i - 1]
        l_diff = lows[i - 1] - lows[i]
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        plus_dm[i] = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
        minus_dm[i] = l_diff if l_diff > h_diff and l_diff > 0 else 0.0

    # Wilder smoothing (RMA)
    def _wilder(arr: np.ndarray) -> np.ndarray:
        out = np.zeros(n)
        out[period] = float(np.sum(arr[1: period + 1]))
        for i in range(period + 1, n):
            out[i] = out[i - 1] - out[i - 1] / period + arr[i]
        return out

    atr14 = _wilder(tr)
    pdm14 = _wilder(plus_dm)
    mdm14 = _wilder(minus_dm)

    # DI+ / DI-
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        di_plus = np.where(atr14 > 0, 100.0 * pdm14 / atr14, 0.0)
        di_minus = np.where(atr14 > 0, 100.0 * mdm14 / atr14, 0.0)

    # DX
    di_sum = di_plus + di_minus
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        dx = np.where(di_sum > 0, 100.0 * np.abs(di_plus - di_minus) / di_sum, 0.0)

    # ADX = Wilder EMA of DX
    adx = np.zeros(n)
    start = period * 2
    if start >= n:
        return result
    adx[start] = float(np.mean(dx[period: period * 2 + 1]))
    for i in range(start + 1, n):
        adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    for i in range(start, n):
        result[i] = float(round(adx[i], 4))

    return result
