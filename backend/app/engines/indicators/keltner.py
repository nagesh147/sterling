import numpy as np
from numpy.typing import NDArray
from typing import Tuple
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.atr import compute_atr


def keltner(
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    close: NDArray[np.float64],
    ema_period: int = 20,
    atr_period: int = 10,
    mult: float = 1.5,
) -> Tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Returns (lower, mid, upper). Used for BB+KC squeeze detection."""
    mid = compute_ema(close, ema_period)
    atr_vals = compute_atr(high, low, close, atr_period)
    upper = mid + mult * atr_vals
    lower = mid - mult * atr_vals
    return lower, mid, upper
