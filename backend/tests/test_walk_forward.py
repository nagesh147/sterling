import pytest
from app.engines.analytics.walk_forward import WalkForwardConfig, run


def _make_candles(n: int) -> list:
    """Simple ascending price candles."""
    import math
    return [
        {
            'close': 100.0 + math.sin(i * 0.1) * 5 + i * 0.1,
            'regime': 'BULL_TREND' if i % 3 == 0 else 'NEUTRAL',
        }
        for i in range(n)
    ]


def test_wf_window_count():
    candles = _make_candles(200)
    cfg = WalkForwardConfig(train_bars=60, test_bars=20, step_bars=10, underlying='BTC')
    result = run(candles, cfg)
    # From idx=0: windows until idx + 60 + 20 > 200
    # idx can be 0,10,20,...,120 → that's 13 windows
    assert len(result.windows) >= 1
    assert len(result.windows) <= 20


def test_wf_no_lookahead():
    """Threshold selection must use only train window — verify by checking window structure."""
    candles = _make_candles(300)
    cfg = WalkForwardConfig(train_bars=100, test_bars=40, step_bars=20, underlying='BTC')
    result = run(candles, cfg)
    for w in result.windows:
        # test_start must be >= train_end (= train_start + train_bars)
        assert w.test_start >= w.train_start + cfg.train_bars


def test_wf_equity_curve_length():
    candles = _make_candles(200)
    cfg = WalkForwardConfig(train_bars=60, test_bars=20, step_bars=10, underlying='BTC')
    result = run(candles, cfg)
    assert len(result.oos_equity_curve) >= 1


def test_wf_recommended_threshold_range():
    candles = _make_candles(300)
    cfg = WalkForwardConfig(
        train_bars=100, test_bars=40, step_bars=20,
        score_thresholds_to_test=[65, 70, 75, 80, 85],
        underlying='BTC',
    )
    result = run(candles, cfg)
    assert 65 <= result.recommended_threshold <= 85
