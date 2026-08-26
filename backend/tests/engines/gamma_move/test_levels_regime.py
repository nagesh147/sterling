"""Levels, and the direction gate."""
from __future__ import annotations

from app.engines.gamma_move import (Candle, GammaMoveConfig, find_levels, live_levels,
                                    option_type_for, regime_allows, regime_of)
from tests.engines.gamma_move.conftest import BASE_MS, DAY_MS

CFG = GammaMoveConfig()


def series_with_pivots():
    """A flat range with three clear highs at 105 and lows at 95."""
    out = []
    for i in range(80):
        high = 105.0 if i in (10, 30, 50) else 101.0
        low = 95.0 if i in (20, 40, 60) else 99.0
        out.append(Candle(ts_ms=BASE_MS + i * DAY_MS, open=100, high=high, low=low,
                          close=100))
    return out


def test_finds_both_sides():
    lv = find_levels(series_with_pivots(), pivot_lookback=3, min_touches=2)
    kinds = {l.kind for l in lv}
    assert "resistance" in kinds and "support" in kinds


def test_unconfirmed_pivots_are_excluded():
    """A pivot at bar i is not knowable until i + lookback bars have printed.
    Using one earlier is lookahead."""
    bars = series_with_pivots()
    # Put a fresh high on the very last bar; it cannot be confirmed yet.
    bars[-1] = Candle(ts_ms=bars[-1].ts_ms, open=100, high=999.0, low=99, close=100)
    lv = find_levels(bars, pivot_lookback=3, min_touches=1)
    assert all(l.price < 900 for l in lv)


def test_proximity_selects_only_what_spot_is_sitting_on():
    lv = find_levels(series_with_pivots(), pivot_lookback=3, min_touches=2)
    assert live_levels(lv, 105.0, 1.0)          # right on the resistance
    assert not live_levels(lv, 100.0, 1.0)      # mid-range: no level here


def test_zero_proximity_selects_nothing():
    """Guarded in config, but the function must not pretend either."""
    lv = find_levels(series_with_pivots(), pivot_lookback=3, min_touches=2)
    assert live_levels(lv, 105.0, 0.0) == []


def test_resistance_means_call_support_means_put():
    lv = find_levels(series_with_pivots(), pivot_lookback=3, min_touches=2)
    for l in lv:
        assert option_type_for(l) == ("CE" if l.kind == "resistance" else "PE")


def test_regime_gates_both_directions(rising_spot, falling_spot):
    assert regime_of(rising_spot, CFG) == "up"
    assert regime_allows("up", "CE", CFG) and not regime_allows("up", "PE", CFG)
    assert regime_of(falling_spot, CFG) == "down"
    assert regime_allows("down", "PE", CFG) and not regime_allows("down", "CE", CFG)


def test_unknown_regime_blocks():
    """A gate that fails open is not a gate."""
    assert not regime_allows("unknown", "CE", CFG)
    assert not regime_allows("unknown", "PE", CFG)


def test_too_little_history_is_unknown():
    assert regime_of([], CFG) == "unknown"


def test_disabled_gate_allows_everything():
    off = GammaMoveConfig(regime_enabled=False)
    assert regime_allows("unknown", "CE", off)
    assert regime_allows("down", "CE", off)


def test_a_flat_stretch_does_not_manufacture_a_level():
    """A plain >= on both sides makes every bar of a plateau a pivot, producing a
    level with dozens of "touches" from a quiet range. Conviction invented from
    noise is worse than no level at all."""
    flat = [Candle(ts_ms=BASE_MS + i * DAY_MS, open=100, high=101.0, low=99.0,
                   close=100) for i in range(80)]
    assert find_levels(flat, pivot_lookback=3, min_touches=2) == []
