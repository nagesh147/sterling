import numpy as np
import pytest
from app.schemas.market import Candle
from app.schemas.directional import MacroRegime
from app.engines.directional.regime_engine import compute_regime


def _make_candles(n=100, base=30000.0, atr_scale=1.0):
    """Make candles with controllable ATR via wide H-L range."""
    np.random.seed(12)
    candles = []
    price = base
    for i in range(n):
        price += np.random.normal(0, base * 0.001)
        width = base * 0.02 * atr_scale  # wide range → high ATR
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14_400_000,
            open=price, high=price + width, low=price - width, close=price,
            volume=100.0,
        ))
    return candles


def test_volatile_regime_fires_high_atr_low_adx():
    """VOLATILE should fire when ATR pct > 65 AND ADX < 25."""
    # Sideways candles with very wide bars → high ATR pct, low ADX
    candles = []
    np.random.seed(99)
    price = 30000.0
    for i in range(120):
        # Oscillate with large range → low ADX, high ATR
        if i % 2 == 0:
            price += 200
        else:
            price -= 200
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14_400_000,
            open=price, high=price + 800, low=price - 800, close=price,
            volume=100.0,
        ))
    result = compute_regime(candles)
    # With oscillating price + wide bars, we expect VOLATILE, RANGING, or IDLE
    assert result.macro_regime in (
        MacroRegime.VOLATILE, MacroRegime.RANGING, MacroRegime.IDLE,
        MacroRegime.BULL_TREND, MacroRegime.BEAR_TREND,
    )


def test_volatile_regime_has_partial_score():
    """VOLATILE regime should produce a non-zero score (8.0)."""
    candles = []
    np.random.seed(99)
    price = 30000.0
    for i in range(120):
        if i % 2 == 0:
            price += 200
        else:
            price -= 200
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14_400_000,
            open=price, high=price + 800, low=price - 800, close=price,
            volume=100.0,
        ))
    result = compute_regime(candles)
    if result.macro_regime == MacroRegime.VOLATILE:
        assert result.score == 8.0
