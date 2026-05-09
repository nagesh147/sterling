import numpy as np
from app.engines.indicators.heikin_ashi import ha_body_bull


def test_ha_body_bull_returns_bool_array():
    n = 20
    o = np.full(n, 100.0)
    h = np.full(n, 110.0)
    l = np.full(n, 90.0)
    c = np.full(n, 105.0)
    result = ha_body_bull(o, h, l, c)
    assert result.dtype == np.bool_
    assert len(result) == n


def test_strongly_bullish_candles():
    """Consistently rising candles → all HA bodies should be bullish."""
    n = 30
    base = np.arange(n, dtype=float) * 10 + 100
    o = base
    h = base + 5
    l = base - 1
    c = base + 4
    result = ha_body_bull(o, h, l, c)
    # After warmup, all should be bullish
    assert np.all(result[5:])


def test_strongly_bearish_candles():
    """Consistently falling candles → HA bodies should be bearish."""
    n = 30
    base = (np.arange(n, dtype=float) * -10) + 500
    o = base + 1
    h = base + 5
    l = base - 5
    c = base
    result = ha_body_bull(o, h, l, c)
    # After warmup, all should be bearish
    assert not np.any(result[10:])


def test_output_shape():
    n = 50
    o = np.random.rand(n) * 100 + 1000
    h = o + 10
    l = o - 10
    c = o + 5
    result = ha_body_bull(o, h, l, c)
    assert len(result) == n
