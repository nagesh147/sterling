import pytest
from app.engines.analytics.sensitivity import sweep, SWEEP_PARAMS


def _make_candles(n: int) -> list:
    return [{'close': 100.0 + i * 0.05, 'regime': 'BULL'} for i in range(n)]


def test_sweep_returns_all_values():
    candles = _make_candles(100)
    values = [65, 70, 75, 80]
    result = sweep(candles, 'score_min', values, {'score_min': 72})
    assert len(result.sharpes) == len(values)
    assert result.values_tested == values


def test_sensitivity_score_nonneg():
    candles = _make_candles(100)
    result = sweep(candles, 'adx_threshold', [20, 25, 30], {'score_min': 72})
    assert result.sensitivity >= 0.0
