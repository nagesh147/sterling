import numpy as np
from app.engines.indicators.keltner import keltner


def _make_ohlc(n=50, base=30000.0):
    np.random.seed(7)
    c = base + np.cumsum(np.random.normal(0, 50, n))
    h = c + np.abs(np.random.normal(0, 30, n))
    l = c - np.abs(np.random.normal(0, 30, n))
    return h, l, c


def test_lower_lt_mid_lt_upper():
    h, l, c = _make_ohlc(60)
    lo, mid, hi = keltner(h, l, c, ema_period=20, atr_period=10, mult=1.5)
    # After warmup, lower < mid < upper
    warmup = 20
    assert np.all(lo[warmup:] < mid[warmup:])
    assert np.all(mid[warmup:] < hi[warmup:])


def test_output_arrays_same_length():
    h, l, c = _make_ohlc(60)
    lo, mid, hi = keltner(h, l, c)
    assert len(lo) == len(c)
    assert len(mid) == len(c)
    assert len(hi) == len(c)


def test_symmetric_around_mid():
    h, l, c = _make_ohlc(60)
    lo, mid, hi = keltner(h, l, c)
    warmup = 20
    # hi - mid should equal mid - lo (symmetric)
    upper_half = hi[warmup:] - mid[warmup:]
    lower_half = mid[warmup:] - lo[warmup:]
    np.testing.assert_allclose(upper_half, lower_half, rtol=1e-10)
