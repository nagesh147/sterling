import numpy as np
from numpy.typing import NDArray
from typing import Tuple
from app.engines.indicators.atr import compute_atr


def compute_supertrend(
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
    closes: NDArray[np.float64],
    period: int,
    multiplier: float,
) -> Tuple[NDArray[np.float64], NDArray[np.int64]]:
    """
    Returns (supertrend_line, trend_array).
    trend: +1 = bullish, -1 = bearish.
    """
    n = len(closes)
    atr = compute_atr(highs, lows, closes, period)
    hl2 = (highs + lows) / 2.0

    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = np.zeros(n)
    trend = np.zeros(n, dtype=np.int64)

    start = period
    if start >= n:
        return supertrend, trend

    trend[start] = 1

    for i in range(start + 1, n):
        prev_close = closes[i - 1]

        final_upper[i] = (
            basic_upper[i]
            if basic_upper[i] < final_upper[i - 1] or prev_close > final_upper[i - 1]
            else final_upper[i - 1]
        )
        final_lower[i] = (
            basic_lower[i]
            if basic_lower[i] > final_lower[i - 1] or prev_close < final_lower[i - 1]
            else final_lower[i - 1]
        )

        if trend[i - 1] == 1:
            trend[i] = -1 if closes[i] < final_lower[i] else 1
        else:
            trend[i] = 1 if closes[i] > final_upper[i] else -1

        supertrend[i] = final_lower[i] if trend[i] == 1 else final_upper[i]

    return supertrend, trend
