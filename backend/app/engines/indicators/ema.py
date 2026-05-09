import numpy as np
from numpy.typing import NDArray
from typing import Tuple


def compute_ema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Standard EMA with SMA seed for first period bars."""
    n = len(values)
    ema = np.zeros(n)
    if n < period:
        return ema

    k = 2.0 / (period + 1)
    ema[period - 1] = float(np.mean(values[:period]))
    for i in range(period, n):
        ema[i] = values[i] * k + ema[i - 1] * (1.0 - k)

    return ema


def ema_dual(
    close: NDArray[np.float64], fast: int = 21, slow: int = 55
) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Returns (ema_fast, ema_slow). Used for dual-EMA crossover regime."""
    return compute_ema(close, fast), compute_ema(close, slow)
