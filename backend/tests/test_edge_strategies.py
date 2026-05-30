"""Parity tests for the shared edge strategy module.

`app/engines/edge/strategies.py` is the single source of truth that BOTH
`comprehensive_backtest.py` and the live edge signal feed import. The edge
numbers in BACKTEST_EDGE_REPORT.md are only trustworthy if the live signal
logic is byte-identical to what the backtest validated.

These tests embed the *reference* implementations (copied verbatim from the
backtest at extraction time) and assert the shared module reproduces them
exactly on seeded random OHLCV data. If anyone "improves" the shared signal
logic without re-running the backtest, these fail — by design.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.engines.edge import strategies as S


def _seeded_ohlc(n: int = 2000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, size=n).cumsum()
    close = 100.0 + steps
    open_ = close + rng.normal(0, 0.3, size=n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.5, size=n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.5, size=n))
    vol = np.abs(rng.normal(1000, 100, size=n))
    idx = pd.date_range("2024-01-01", periods=n, freq="4h")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


# --- Reference implementations (verbatim copies, frozen) -------------------

def _ref_ma_crossover(df):
    fast = df["close"].ewm(span=9, adjust=False).mean()
    slow = df["close"].ewm(span=21, adjust=False).mean()
    bull = fast > slow
    return (bull & ~bull.shift(1).fillna(False)).to_numpy()


def _ref_mean_reversion(df):
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    cross_up = (rsi > 30) & (rsi.shift(1) <= 30)
    return cross_up.fillna(False).to_numpy()


def _ref_breakout(df):
    hh = df["high"].rolling(20).max().shift(1)
    cross = df["close"] > hh
    return (cross & ~cross.shift(1).fillna(False)).fillna(False).to_numpy()


def _ref_price_action(df):
    prev_bear = df["close"].shift(1) < df["open"].shift(1)
    curr_bull = df["close"] > df["open"]
    engulf = (df["close"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1))
    return (prev_bear & curr_bull & engulf).fillna(False).to_numpy()


def _ref_smc(df):
    gap = df["low"] - df["high"].shift(2)
    curr_bull = df["close"] > df["open"]
    return ((gap > 0) & curr_bull).fillna(False).to_numpy()


_REFS = {
    "ma_crossover": _ref_ma_crossover,
    "mean_reversion": _ref_mean_reversion,
    "breakout": _ref_breakout,
    "price_action": _ref_price_action,
    "smc": _ref_smc,
}


@pytest.mark.parametrize("name", sorted(_REFS))
def test_signal_fn_matches_reference(name):
    df = _seeded_ohlc()
    got = S.SIGNAL_FNS[name](df)
    expected = _REFS[name](df)
    assert got.dtype == bool or got.dtype == np.bool_
    np.testing.assert_array_equal(got, expected)


def test_atr14_matches_reference():
    df = _seeded_ohlc()
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    expected = tr.rolling(14).mean()
    got = S.atr14(df)
    pd.testing.assert_series_equal(got, expected, check_names=False)


def test_strategy_names_complete():
    assert set(S.SIGNAL_FNS) == set(_REFS)
