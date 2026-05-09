import numpy as np
from numpy.typing import NDArray
from typing import Tuple


def ha_body_bull(
    open_: NDArray[np.float64],
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    close: NDArray[np.float64],
) -> NDArray[np.bool_]:
    """Returns bool array: True where HA candle body is bullish."""
    ha_c = (open_ + high + low + close) / 4
    ha_o = np.empty_like(open_)
    ha_o[0] = open_[0]
    for i in range(1, len(open_)):
        ha_o[i] = (ha_o[i - 1] + ha_c[i - 1]) / 2
    return ha_c > ha_o


def compute_heikin_ashi(
    opens: NDArray[np.float64],
    highs: NDArray[np.float64],
    lows: NDArray[np.float64],
    closes: NDArray[np.float64],
) -> Tuple[NDArray, NDArray, NDArray, NDArray]:
    """Convert OHLC to Heikin-Ashi OHLC."""
    n = len(closes)
    ha_close = (opens + highs + lows + closes) / 4.0
    ha_open = np.zeros(n)
    ha_open[0] = (opens[0] + closes[0]) / 2.0
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    ha_high = np.maximum(highs, np.maximum(ha_open, ha_close))
    ha_low = np.minimum(lows, np.minimum(ha_open, ha_close))
    return ha_open, ha_high, ha_low, ha_close
