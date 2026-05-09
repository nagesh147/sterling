import numpy as np
import pytest
from app.engines.indicators.atr import atr_percentile, compute_atr


def test_returns_50_on_insufficient_data():
    """Less than 5 valid values → defaults to 50.0."""
    tiny = np.array([0.0, 0.0, 0.0, 1.0, np.nan])
    result = atr_percentile(tiny, lookback=100)
    assert result == 50.0


def test_returns_high_when_current_greatest():
    """When current ATR is larger than all other history, percentile is high.
    Note: self-comparison means max = (n-1)/n * 100, not 100."""
    base = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 10.0])
    result = atr_percentile(base, lookback=100)
    # 10 > [1,2,3,4,5] (5 out of 6 including self), so 5/6*100 ≈ 83.3
    assert result > 80.0


def test_returns_0_when_current_smallest():
    """When current ATR is smallest, percentile approaches 0."""
    base = np.array([10.0, 9.0, 8.0, 7.0, 6.0, 1.0])
    result = atr_percentile(base, lookback=100)
    assert result == 0.0


def test_returns_float():
    atr_arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 3.0])
    result = atr_percentile(atr_arr, lookback=100)
    assert isinstance(result, float)


def test_lookback_window():
    """Should only compare against last lookback bars."""
    # First 100 bars high, last 6 bars low
    arr = np.concatenate([np.full(100, 100.0), np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])])
    result = atr_percentile(arr, lookback=6)
    # Within the lookback of 6, current 1.0 equals all others
    assert result == 0.0
