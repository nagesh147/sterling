import numpy as np
from numpy.typing import NDArray


def atr_percentile(atr: NDArray[np.float64], lookback: int = 100) -> float:
    """Current ATR as percentile rank vs trailing lookback bars. Returns 0-100."""
    recent = atr[-lookback:]
    valid = recent[~np.isnan(recent)]
    if len(valid) < 5 or np.isnan(atr[-1]):
        return 50.0
    return float(np.sum(atr[-1] > valid) / len(valid) * 100)


def compute_atr(
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
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
            abs(lows[i] - closes[i - 1]),
        )

    atr = np.zeros(n)
    if n <= period:
        return atr

    atr[period] = float(np.mean(tr[1 : period + 1]))
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr
