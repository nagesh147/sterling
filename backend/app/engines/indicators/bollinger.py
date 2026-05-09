import numpy as np
from numpy.typing import NDArray
from typing import Tuple


def bollinger_bands(
    close: NDArray[np.float64],
    period: int = 20,
    std_mult: float = 2.0,
) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Returns (lower, mid, upper). Mid is SMA, bands use sample std."""
    n = len(close)
    mid = np.zeros(n)
    upper = np.zeros(n)
    lower = np.zeros(n)
    for i in range(period - 1, n):
        window = close[i - period + 1:i + 1]
        m = float(np.mean(window))
        s = float(np.std(window, ddof=1)) if period > 1 else 0.0
        mid[i] = m
        upper[i] = m + std_mult * s
        lower[i] = m - std_mult * s
    return lower, mid, upper
