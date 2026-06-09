"""Regime book — classifier, short sleeves, router, portfolio sim, walk-forward."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from study.regime_book import classify_regime


def _frame(closes, atr=None):
    closes = np.asarray(closes, float)
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    high = closes * 1.005
    low = closes * 0.995
    df = pd.DataFrame({"open": closes, "high": high, "low": low,
                       "close": closes, "volume": 1.0}, index=idx)
    df["atr"] = (high - low) if atr is None else atr
    return df


def test_uptrend_classified_positive():
    df = _frame(np.linspace(100, 200, 300))   # steady rise
    reg = classify_regime(df, adx_threshold=20.0, ma_window=50)
    # After warmup, a clean uptrend is regime +1 for most bars.
    assert (reg[100:] == 1).mean() > 0.7


def test_downtrend_classified_negative():
    df = _frame(np.linspace(200, 100, 300))
    reg = classify_regime(df, adx_threshold=20.0, ma_window=50)
    assert (reg[100:] == -1).mean() > 0.7


def test_classifier_has_no_lookahead():
    """Truncating the future cannot change an earlier bar's regime label."""
    df = _frame(np.r_[np.linspace(100, 200, 200), np.linspace(200, 100, 200)])
    full = classify_regime(df, adx_threshold=20.0, ma_window=50)
    trunc = classify_regime(df.iloc[:250], adx_threshold=20.0, ma_window=50)
    assert np.array_equal(full[:250], trunc)


# --- Task 2: short sleeve signals ---------------------------------------
from study.regime_book import short_momentum, short_mean_reversion


def test_short_momentum_fires_on_bearish_cross():
    # rise then fall: a bearish 9/21 EMA cross must appear on the way down.
    df = _frame(np.r_[np.linspace(100, 160, 120), np.linspace(160, 90, 120)])
    sig = short_momentum(df)
    assert sig.dtype == bool and len(sig) == len(df)
    assert sig[120:].any()          # fires during the decline
    assert not sig[:60].any()       # not during the clean rise


def test_short_mean_reversion_fires_on_upper_band_fade():
    # Noisy mean-reverting series, then an overbought rally that rejects the
    # upper band and reverts. Noise keeps RSI finite (a pure monotonic leg makes
    # RSI undefined/zero — a fixture artifact, not what real bars look like).
    rng = np.random.default_rng(1)
    base = 100 + np.cumsum(rng.normal(0, 0.5, 120))
    rally = base[-1] + np.cumsum(np.abs(rng.normal(0.9, 0.4, 25)))   # strong up
    revert = rally[-1] - np.cumsum(np.abs(rng.normal(0.9, 0.4, 25)))  # fade down
    df = _frame(np.r_[base, rally, revert])
    sig = short_mean_reversion(df)
    assert sig.dtype == bool and len(sig) == len(df)
    assert sig[120:].any()
