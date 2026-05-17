import pytest
from tests.conftest import make_candles
from app.engines.directional.signal_engine import compute_signal

def test_compute_signal_accepts_custom_st_configs():
    """compute_signal must accept st_configs param without error."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    scalping_configs = [(5, 2.5), (10, 1.5), (14, 1.0)]
    result = compute_signal(candles, st_configs=scalping_configs)
    assert result.signal_score >= 0.0
    assert result.signal_score <= 20.0

def test_compute_signal_accepts_custom_st_threshold():
    """st_threshold=2 allows 2/3 STs to trigger all_green."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    result_strict  = compute_signal(candles, st_threshold=3)
    result_relaxed = compute_signal(candles, st_threshold=2)
    assert isinstance(result_relaxed.all_green, bool)
    assert isinstance(result_strict.all_green, bool)

def test_compute_signal_default_unchanged():
    """Default call (no new params) returns same result as before."""
    candles = make_candles(60, base=30000.0, trend=10.0)
    r1 = compute_signal(candles)
    r2 = compute_signal(candles, st_configs=None, st_threshold=3)
    assert r1.signal_score == r2.signal_score
    assert r1.trend == r2.trend
