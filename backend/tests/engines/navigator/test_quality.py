import numpy as np
import pytest

from app.engines.navigator.quality import CandleValidationError, ist_calendar_dates, validate_candles
from tests.engines.navigator.conftest import make_candles


def _good_bars(n=5):
    o = [100.0] * n
    h = [101.0] * n
    l = [99.0] * n
    c = [100.5] * n
    v = [1000.0] * n
    return o, h, l, c, v


class TestValidateCandles:
    def test_accepts_clean_series(self):
        o, h, l, c, v = _good_bars()
        vc = validate_candles(make_candles(o, h, l, c, v))
        assert vc.n == 5

    def test_rejects_empty(self):
        with pytest.raises(CandleValidationError):
            validate_candles([])

    def test_rejects_high_below_close(self):
        o, h, l, c, v = _good_bars()
        h[2] = 90.0  # below close[2]=100.5
        with pytest.raises(CandleValidationError):
            validate_candles(make_candles(o, h, l, c, v))

    def test_rejects_low_above_open(self):
        o, h, l, c, v = _good_bars()
        l[2] = 105.0  # above open[2]=100
        with pytest.raises(CandleValidationError):
            validate_candles(make_candles(o, h, l, c, v))

    def test_rejects_negative_volume(self):
        o, h, l, c, v = _good_bars()
        v[1] = -5.0
        with pytest.raises(CandleValidationError):
            validate_candles(make_candles(o, h, l, c, v))

    def test_rejects_negative_price(self):
        o, h, l, c, v = _good_bars()
        l[0] = -1.0
        with pytest.raises(CandleValidationError):
            validate_candles(make_candles(o, h, l, c, v))

    def test_rejects_non_finite_value(self):
        o, h, l, c, v = _good_bars()
        c[3] = float("nan")
        with pytest.raises(CandleValidationError):
            validate_candles(make_candles(o, h, l, c, v))

    def test_rejects_duplicate_timestamp(self):
        candles = make_candles(*_good_bars())
        candles[2] = candles[2].model_copy(update={"timestamp_ms": candles[1].timestamp_ms})
        with pytest.raises(CandleValidationError):
            validate_candles(candles)

    def test_rejects_out_of_order_timestamps(self):
        candles = make_candles(*_good_bars())
        candles[1], candles[2] = candles[2], candles[1]
        with pytest.raises(CandleValidationError):
            validate_candles(candles)

    def test_typical_price_formula(self):
        vc = validate_candles(make_candles(*_good_bars(1)))
        expected = (101.0 + 99.0 + 100.5) / 3.0
        assert vc.typical_price()[0] == pytest.approx(expected)


class TestIstCalendarDates:
    def test_same_ist_day_bars_share_a_date(self):
        ts = np.array([1_753_000_000_000, 1_753_000_000_000 + 3_600_000])
        dates = ist_calendar_dates(ts)
        assert dates[0] == dates[1]

    def test_next_day_bar_has_a_different_date(self):
        ts = np.array([1_753_000_000_000, 1_753_000_000_000 + 24 * 3_600_000])
        dates = ist_calendar_dates(ts)
        assert dates[0] != dates[1]
