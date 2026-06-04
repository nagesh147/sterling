"""Tests for the two macro-timeframe fixes on the Sterling Engine:

1. `_relabel_macro_tf` — reason strings hardcode "4H" but must reflect the
   profile's actual macro timeframe (1h / 15m / 1d).
2. `_resample_candles` — the swing_4h profile's 1d macro is resampled from stored
   4h candles (the fetcher doesn't keep daily), so the profile isn't silently dead.
"""
from app.engines.sterling_engine.scanner import _relabel_macro_tf
from app.api.v1.endpoints.sterling_engine import _resample_candles
from app.schemas.market import Candle


def test_relabel_swaps_4h_for_active_macro():
    assert _relabel_macro_tf("no nearby 4H level", "1h") == "no nearby 1H level"
    assert _relabel_macro_tf("near 4H support 100 · R:R", "15m") == "near 15M support 100 · R:R"
    assert _relabel_macro_tf("no nearby 4H liquidity zone", "1d") == "no nearby 1D liquidity zone"


def test_relabel_noop_when_already_4h_or_empty():
    assert _relabel_macro_tf("no nearby 4H level", "4h") == "no nearby 4H level"
    assert _relabel_macro_tf("", "1h") == ""
    assert _relabel_macro_tf(None, "1h") is None


def test_relabel_is_word_boundary_safe():
    # only the standalone "4H" token is relabeled, never a substring of a number/word
    assert _relabel_macro_tf("EMA9×EMA21 cross", "1h") == "EMA9×EMA21 cross"
    assert _relabel_macro_tf("priced 1234H units", "1h") == "priced 1234H units"


def _c(ts_s, o, h, l, cl, v=1.0):
    return Candle(timestamp_ms=ts_s * 1000, open=o, high=h, low=l, close=cl, volume=v)


def test_resample_4h_to_daily_ohlcv():
    day0 = 1_700_000_000 // 86400 * 86400  # align to a UTC midnight
    bars = []
    for d in range(2):
        for k in range(6):  # 6 × 4h = 1 day
            ts = day0 + d * 86400 + k * 14400
            bars.append(_c(ts, o=100 + k, h=110 + k, l=90 + k, cl=105 + k, v=2.0))
    daily = _resample_candles(bars, 86400)

    assert len(daily) == 2
    d0 = daily[0]
    assert d0.timestamp_ms == day0 * 1000  # bucket aligned to 00:00 UTC
    assert d0.open == 100                   # first 4h bar's open (k=0)
    assert d0.close == 110                  # last 4h bar's close (k=5 → 105+5)
    assert d0.high == 115                   # max high (k=5 → 110+5)
    assert d0.low == 90                     # min low (k=0 → 90+0)
    assert d0.volume == 12.0                # 6 bars × 2.0


def test_resample_empty_input():
    assert _resample_candles([], 86400) == []
