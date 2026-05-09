import numpy as np
import pytest
from app.engines.indicators.adx import adx


def _make_ohlc(n=100, base=30000.0, trend=50.0):
    np.random.seed(42)
    h, l, c = [], [], []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.001)
        h.append(price + abs(np.random.normal(0, base * 0.002)))
        l.append(price - abs(np.random.normal(0, base * 0.002)))
        c.append(price)
    return np.array(h), np.array(l), np.array(c)


def test_adx_output_shape():
    h, l, c = _make_ohlc(100)
    result = adx(h, l, c, 14)
    assert len(result) == 100


def test_adx_no_nan_beyond_warmup():
    h, l, c = _make_ohlc(100)
    result = adx(h, l, c, 14)
    warmup = 14 * 2
    assert not np.any(np.isnan(result[warmup:]))


def test_adx_value_range():
    h, l, c = _make_ohlc(150)
    result = adx(h, l, c, 14)
    valid = result[result > 0]
    assert np.all(valid >= 0.0)
    assert np.all(valid <= 100.0)


def test_adx_insufficient_data_returns_zeros():
    h, l, c = _make_ohlc(10)
    result = adx(h, l, c, 14)
    assert np.all(result == 0.0)


def test_adx_strong_trend_has_high_adx():
    """Strong trending data should produce ADX well above 25."""
    n = 150
    h = np.array([i * 100.0 + 50 for i in range(n)])
    l = np.array([i * 100.0 for i in range(n)])
    c = np.array([i * 100.0 + 25 for i in range(n)])
    result = adx(h, l, c, 14)
    # Near the end, ADX should be elevated
    assert result[-1] > 25.0
