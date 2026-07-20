import numpy as np
import pytest


def series(values):
    """Build OHLC arrays from a close path; tight bars so HA tracks closely."""
    c = np.asarray(values, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + 1.0
    l = np.minimum(o, c) - 1.0
    return o, h, l, c


@pytest.fixture
def uptrend():
    # long, smooth rise — drives all three SuperTrends bullish after warmup
    return series(list(np.linspace(100, 400, 120)))


@pytest.fixture
def down_then_up():
    # falling then rising — produces a bear→bull transition
    fall = list(np.linspace(300, 150, 60))
    rise = list(np.linspace(150, 450, 60))
    return series(fall + rise)
