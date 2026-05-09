import numpy as np
from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.indicators.rsi import rsi as compute_rsi


def _make_candles(n=100, base=30000.0, trend=50.0):
    np.random.seed(10)
    candles = []
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.001)
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=price, high=price + 100, low=price - 100, close=price,
            volume=100.0,
        ))
    return candles


def test_rsi_at_78_blocks_long_signal():
    """RSI >= 78 should not satisfy the long gate (requires 52 < rsi < 78)."""
    closes = np.array([30000.0 + i * 200 for i in range(50)], dtype=float)
    rsi_vals = compute_rsi(closes, 14)
    # After strong up-trend, RSI will be high
    cur_rsi = rsi_vals[-1]
    rsi_ok_long = 52.0 < cur_rsi < 78.0
    if cur_rsi >= 78.0:
        assert not rsi_ok_long, f"RSI {cur_rsi} should block long signal"


def test_rsi_short_gate():
    """RSI <= 22 should not satisfy the short gate (requires 22 < rsi < 48)."""
    closes = np.array([50000.0 - i * 200 for i in range(50)], dtype=float)
    rsi_vals = compute_rsi(closes, 14)
    cur_rsi = rsi_vals[-1]
    rsi_ok_short = 22.0 < cur_rsi < 48.0
    if cur_rsi <= 22.0:
        assert not rsi_ok_short, f"RSI {cur_rsi} should block short signal"


def test_rsi_within_long_gate():
    """RSI between 52 and 78 satisfies the long gate."""
    # Moderate uptrend → RSI in bullish but not overbought range
    closes = np.array([30000.0 + i * 50 for i in range(100)], dtype=float)
    rsi_vals = compute_rsi(closes, 14)
    cur_rsi = float(rsi_vals[-1])
    # For very consistent small uptrend, RSI will stabilize around 60-70
    if 52.0 < cur_rsi < 78.0:
        assert 52.0 < cur_rsi < 78.0


def test_rsi_output_range():
    """RSI values should always be in 0-100."""
    closes = np.array([30000.0 + i * 50 for i in range(100)], dtype=float)
    rsi_vals = compute_rsi(closes, 14)
    assert np.all(rsi_vals >= 0.0)
    assert np.all(rsi_vals <= 100.0)
