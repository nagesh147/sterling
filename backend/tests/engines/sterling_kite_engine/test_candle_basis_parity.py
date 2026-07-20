import numpy as np

from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime


def _ohlc():
    close = np.array(
        list(np.linspace(230.0, 95.0, 32))
        + [105, 118, 112, 126, 140, 154, 168, 182, 176, 190, 205, 198, 212, 226, 220, 235],
        dtype=float,
    )
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.linspace(4.0, 13.0, len(close))
    low = np.minimum(open_, close) - np.linspace(3.0, 9.0, len(close))
    return open_, high, low, close


def test_default_regime_matches_regular_zerodha_candles():
    o, h, l, c = _ohlc()
    cfg = SterlingKiteEngineConfig()

    regime = compute_regime(o, h, l, c, cfg)
    expected = [
        compute_supertrend(h, l, c, period, multiplier)
        for period, multiplier in (cfg.fast, cfg.mid, cfg.slow)
    ]

    assert cfg.candle_basis == "raw"
    assert np.array_equal(regime.l_fast, expected[0][0])
    assert np.array_equal(regime.t_fast, expected[0][1])
    assert np.array_equal(regime.l_mid, expected[1][0])
    assert np.array_equal(regime.t_mid, expected[1][1])
    assert np.array_equal(regime.l_slow, expected[2][0])
    assert np.array_equal(regime.t_slow, expected[2][1])


def test_heikin_ashi_remains_explicitly_available():
    o, h, l, c = _ohlc()
    cfg = SterlingKiteEngineConfig(candle_basis="heikin_ashi")

    regime = compute_regime(o, h, l, c, cfg)
    _, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    expected_fast = compute_supertrend(ha_h, ha_l, ha_c, *cfg.fast)

    assert np.array_equal(regime.l_fast, expected_fast[0])
    assert np.array_equal(regime.t_fast, expected_fast[1])
