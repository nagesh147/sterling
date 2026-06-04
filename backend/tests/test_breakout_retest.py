"""Breakout retest entry — the rebuilt breakout strategy.

The old breakout CHASED the extended breakout candle (entry at the high, stop at
the just-broken level) and was stopped out 44/44 times. The rebuilt version waits
for the break, then for price to PULL BACK and retest the broken level, and
enters on the hold with a tight stop just beyond the level. That gives an entry
near support (not the extension) and a logical, tight stop.
"""
from __future__ import annotations

import types

from app.engines.sterling_engine.breakout import evaluate_breakout
from app.engines.sterling_engine.config import ScalpingProfile
from app.engines.sterling_engine.levels import Level


def _c(ts, o, h, l, cl, v=100.0):
    return types.SimpleNamespace(timestamp_ms=ts, open=o, high=h, low=l, close=cl, volume=v)


def _level(price, ltype):
    return Level(price=price, touches=3, first_touch_ts=0, last_touch_ts=0, level_type=ltype)


def _macro(n=30):
    return [_c(i * 4 * 3_600_000, 100, 101, 99, 100) for i in range(n)]


def _long_retest_series():
    """Below a 100 resistance, then a break above (highs ~102), then a pullback
    that retests 100 from above and closes up on the current bar."""
    q = 900_000
    bars = []
    t = 0
    # 30 bars consolidating just below the 100 level
    for i in range(30):
        bars.append(_c(t, 98.6, 99.2, 98.2, 98.8)); t += q
    # 4-bar breakout thrust above the level (highs clearly above 100 + tolerance)
    for hi in (101.2, 102.0, 101.6, 101.0):
        bars.append(_c(t, hi - 0.6, hi, hi - 0.9, hi - 0.3)); t += q
    # pullback toward the level
    for cl in (100.8, 100.5):
        bars.append(_c(t, cl + 0.3, cl + 0.4, cl - 0.2, cl)); t += q
    # current bar: retests 100 (low dips to ~100.1) and closes UP at 100.3
    bars.append(_c(t, 100.15, 100.45, 100.05, 100.30))
    return bars


def test_retest_fires_long_with_stop_below_level():
    cfg = ScalpingProfile(enable_breakout=True)
    sig = evaluate_breakout("BTC", _macro(), _long_retest_series(), [_level(100.0, "resistance")], cfg)
    assert sig.entry_ok is True
    assert sig.direction == "long"
    assert "retest" in sig.pattern.lower() or "retest" in sig.reason.lower()
    # entry sits near the level (a retest), NOT chased far above it
    assert sig.entry is not None and 100.0 <= sig.entry <= 100.6
    # stop is below the retested level (now support)
    assert sig.stop_loss is not None and sig.stop_loss < 100.0
    # logical R:R — target above entry
    assert sig.take_profit is not None and sig.take_profit > sig.entry


def test_no_retest_when_price_still_extended():
    """If price never pulled back (still up at the extension), no retest entry."""
    cfg = ScalpingProfile(enable_breakout=True)
    bars = _long_retest_series()
    # replace the current bar with one still extended at 102 (no pullback)
    bars[-1] = _c(bars[-1].timestamp_ms, 101.8, 102.2, 101.6, 102.0)
    sig = evaluate_breakout("BTC", _macro(), bars, [_level(100.0, "resistance")], cfg)
    assert sig.entry_ok is False


def test_no_signal_without_prior_breakout():
    """Price near the level but it never broke above → not a retest setup."""
    cfg = ScalpingProfile(enable_breakout=True)
    q = 900_000
    bars = [_c(i * q, 99.9, 100.05, 99.7, 99.95) for i in range(40)]  # hugs below, never breaks
    sig = evaluate_breakout("BTC", _macro(), bars, [_level(100.0, "resistance")], cfg)
    assert sig.entry_ok is False
