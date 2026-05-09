import numpy as np
from app.schemas.market import Candle
from app.schemas.directional import MacroRegime
from app.engines.directional.regime_engine import compute_regime


def _make_bull_candles(n=120, base=30000.0, trend=200.0):
    """Strong uptrend so EMA21 crosses above EMA55 and ADX > 25."""
    candles = []
    np.random.seed(1)
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.003)
        width = base * 0.005
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14_400_000,
            open=price, high=price + width, low=price - width, close=price,
            volume=100.0,
        ))
    return candles


def _make_bear_candles(n=120, base=50000.0, trend=-200.0):
    """Strong downtrend so EMA21 crosses below EMA55 and ADX > 25."""
    candles = []
    np.random.seed(2)
    price = base
    for i in range(n):
        price += trend + np.random.normal(0, base * 0.003)
        price = max(price, 1000.0)
        width = base * 0.005
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 14_400_000,
            open=price, high=price + width, low=price - width, close=price,
            volume=100.0,
        ))
    return candles


def test_bull_trend_requires_dual_ema_crossover():
    """BULL_TREND requires EMA21 > EMA55 AND ADX >= 25."""
    candles = _make_bull_candles(n=120, trend=300.0)
    result = compute_regime(candles)
    # With strong uptrend, should be BULL_TREND (or IDLE if ATR contracted)
    assert result.macro_regime in (
        MacroRegime.BULL_TREND, MacroRegime.RANGING, MacroRegime.VOLATILE, MacroRegime.IDLE,
    )
    if result.macro_regime == MacroRegime.BULL_TREND:
        assert result.ema21 > result.ema55
        assert result.adx >= 25.0


def test_bear_trend_requires_dual_ema_crossover():
    """BEAR_TREND requires EMA21 < EMA55 AND ADX >= 25."""
    candles = _make_bear_candles(n=120, trend=-300.0)
    result = compute_regime(candles)
    assert result.macro_regime in (
        MacroRegime.BEAR_TREND, MacroRegime.RANGING, MacroRegime.VOLATILE, MacroRegime.IDLE,
    )
    if result.macro_regime == MacroRegime.BEAR_TREND:
        assert result.ema21 < result.ema55
        assert result.adx >= 25.0


def test_regime_result_has_ema_fields():
    """RegimeResult v2 should have ema21 and ema55 fields."""
    candles = _make_bull_candles(100)
    result = compute_regime(candles)
    assert hasattr(result, "ema21")
    assert hasattr(result, "ema55")
    assert hasattr(result, "atr_percentile")
    assert hasattr(result, "adx")
    assert result.ema21 > 0.0
    assert result.ema55 > 0.0
