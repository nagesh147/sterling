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
