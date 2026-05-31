"""Regime-adaptive ATR stop multiplier.

A static `max_stop_atr` (e.g. 2.0×ATR everywhere) ignores that ATR's *own*
distribution shifts with the volatility regime. This scales the multiplier by
where current ATR sits in its recent range: give turbulent regimes more room
(wider) and tighten in quiet ones — bounded so it can never run away.
"""
from __future__ import annotations

import numpy as np

from app.engines.analytics.adaptive_stops import regime_atr_multiplier


def test_quiet_regime_tightens():
    # current ATR at the bottom of its recent range → multiplier scaled down
    hist = list(np.linspace(10, 20, 50))
    m = regime_atr_multiplier(atr_now=10.0, atr_history=hist, base_mult=2.0)
    assert m < 2.0


def test_turbulent_regime_widens():
    hist = list(np.linspace(10, 20, 50))
    m = regime_atr_multiplier(atr_now=20.0, atr_history=hist, base_mult=2.0)
    assert m > 2.0


def test_median_regime_is_base():
    hist = list(np.linspace(10, 20, 51))  # median = 15
    m = regime_atr_multiplier(atr_now=15.0, atr_history=hist, base_mult=2.0)
    assert abs(m - 2.0) < 1e-9


def test_clamped_to_bounds():
    hist = list(np.linspace(10, 20, 50))
    # extreme high ATR must not blow past max_mult
    hi = regime_atr_multiplier(atr_now=1e6, atr_history=hist, base_mult=2.0,
                               lo_scale=0.7, hi_scale=1.4, min_mult=1.5, max_mult=2.8)
    assert hi == 2.8
    lo = regime_atr_multiplier(atr_now=0.0001, atr_history=hist, base_mult=2.0,
                               lo_scale=0.7, hi_scale=1.4, min_mult=1.5, max_mult=2.8)
    assert lo == 1.5


def test_monotonic_in_atr():
    hist = list(np.linspace(10, 20, 50))
    ms = [regime_atr_multiplier(atr_now=a, atr_history=hist, base_mult=2.0)
          for a in (10, 12, 14, 16, 18, 20)]
    assert all(ms[i] <= ms[i + 1] + 1e-12 for i in range(len(ms) - 1))


def test_insufficient_history_returns_base():
    m = regime_atr_multiplier(atr_now=12.0, atr_history=[11.0], base_mult=2.0)
    assert m == 2.0
