import numpy as np
from numpy.typing import NDArray


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
