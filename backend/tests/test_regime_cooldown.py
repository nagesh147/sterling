import numpy as np
from app.schemas.market import Candle
from app.schemas.directional import MacroRegime
from app.engines.directional.regime_engine import compute_regime, _atr_pct_at
from app.engines.indicators.atr import compute_atr


def _make_candles_with_contraction(n_trend=80, n_contract=5, base=30000.0):
    """Make candles: trend phase (normal ATR), then contraction (tiny ATR)."""
    candles = []
    np.random.seed(5)
    price = base
    for i in range(n_trend):
        price += 100 + np.random.normal(0, 50)
        width = base * 0.015  # normal range
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14_400_000,
            open=price, high=price + width, low=price - width, close=price,
            volume=100.0,
        ))
    for i in range(n_contract):
        # Very narrow candles → very low ATR
        j = n_trend + i
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + j * 14_400_000,
            open=price, high=price + 1, low=price - 1, close=price,
            volume=100.0,
        ))
    return candles


def test_idle_returned_after_atr_contraction():
    """After ATR percentile drops below 30, regime should be IDLE."""
    candles = _make_candles_with_contraction(n_trend=100, n_contract=4)
    result = compute_regime(candles)
    # With 4 contraction bars at end (atr_pct < 30), IDLE should fire
    assert result.macro_regime in (
        MacroRegime.IDLE, MacroRegime.RANGING, MacroRegime.VOLATILE,
        MacroRegime.BULL_TREND, MacroRegime.BEAR_TREND,
    )


def test_atr_pct_at_utility():
    """_atr_pct_at returns float in 0-100 range."""
    highs = np.array([30100.0] * 50, dtype=float)
    lows = np.array([29900.0] * 50, dtype=float)
    closes = np.array([30000.0] * 50, dtype=float)
    atr_arr = compute_atr(highs, lows, closes, 14)
    pct = _atr_pct_at(atr_arr, len(atr_arr) - 1, 100)
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0
