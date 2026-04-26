import numpy as np
import pytest
from app.engines.indicators.atr import compute_atr
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend


def _ohlc(n=100, base=30000.0, trend=10.0):
    np.random.seed(42)
    price = base
    o, h, l, c = [], [], [], []
    for _ in range(n):
        price += trend
        op = price + np.random.normal(0, 50)
        cl = price + np.random.normal(0, 50)
        hi = max(op, cl) + abs(np.random.normal(0, 30))
        lo = min(op, cl) - abs(np.random.normal(0, 30))
        o.append(op); h.append(hi); l.append(lo); c.append(cl)
    return (
        np.array(o), np.array(h), np.array(l), np.array(c)
    )


class TestATR:
    def test_length(self):
        _, h, l, c = _ohlc()
        atr = compute_atr(h, l, c, 14)
        assert len(atr) == len(c)

    def test_positive_values(self):
        _, h, l, c = _ohlc()
        atr = compute_atr(h, l, c, 14)
        assert all(v >= 0 for v in atr)

    def test_short_series_returns_zeros(self):
        h = np.array([1.0, 2.0])
        l = np.array([0.5, 1.0])
        c = np.array([0.8, 1.5])
        atr = compute_atr(h, l, c, 14)
        assert atr[-1] == 0.0


class TestEMA:
    def test_length(self):
        _, _, _, c = _ohlc()
        ema = compute_ema(c, 50)
        assert len(ema) == len(c)

    def test_seed_value(self):
        c = np.arange(1.0, 11.0)
        ema = compute_ema(c, 5)
        assert ema[4] == pytest.approx(np.mean(c[:5]))

    def test_tracks_trend(self):
        _, _, _, c = _ohlc(trend=100.0)
        ema = compute_ema(c, 20)
        assert ema[-1] > ema[20]


class TestHeikinAshi:
    def test_output_shape(self):
        o, h, l, c = _ohlc()
        ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
        assert all(len(x) == len(c) for x in [ha_o, ha_h, ha_l, ha_c])

    def test_ha_high_ge_ha_low(self):
        o, h, l, c = _ohlc()
        _, ha_h, ha_l, _ = compute_heikin_ashi(o, h, l, c)
        assert all(ha_h[i] >= ha_l[i] for i in range(len(c)))

    def test_ha_close_formula(self):
        o = np.array([10.0]); h = np.array([12.0]); l = np.array([8.0]); c = np.array([11.0])
        _, _, _, ha_c = compute_heikin_ashi(o, h, l, c)
        assert ha_c[0] == pytest.approx((10 + 12 + 8 + 11) / 4)


class TestSuperTrend:
    def test_output_shape(self):
        _, h, l, c = _ohlc()
        st, trend = compute_supertrend(h, l, c, 7, 3.0)
        assert len(st) == len(c)
        assert len(trend) == len(c)

    def test_trend_values(self):
        _, h, l, c = _ohlc()
        _, trend = compute_supertrend(h, l, c, 7, 3.0)
        unique = set(int(t) for t in trend)
        assert unique.issubset({-1, 0, 1})

    def test_bullish_trend_dominant(self):
        """Strong uptrend → more +1 than -1."""
        _, h, l, c = _ohlc(n=200, trend=200.0)
        _, trend = compute_supertrend(h, l, c, 7, 3.0)
        bullish = sum(1 for t in trend if t == 1)
        assert bullish > len(trend) // 2
