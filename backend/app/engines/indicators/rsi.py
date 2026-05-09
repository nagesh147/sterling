import numpy as np
from numpy.typing import NDArray


def rsi(close: NDArray[np.float64], period: int = 14) -> NDArray[np.float64]:
    """Wilder RSI. Returns ndarray aligned with close. Warm-up bars default to 50."""
    n = len(close)
    result = np.full(n, 50.0)
    if n <= period:
        return result
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100.0
        result[i + 1] = 100.0 - 100.0 / (1.0 + rs)
    return result
