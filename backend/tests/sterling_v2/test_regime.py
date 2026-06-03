import numpy as np
import pandas as pd
from app.engines.sterling_v2 import regime as R


def _trend_df(n=300):
    idx = pd.date_range("2024-01-01", periods=n, freq="4h")
    c = np.cumprod(1 + np.full(n, 0.002))  # steady uptrend
    o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"open": o, "high": c * 1.001, "low": c * 0.999,
                         "close": c, "volume": 1.0}, index=idx)


def test_gate_allows_in_uptrend_for_long():
    df = _trend_df()
    f = R.build_gate(df, adx_min=0.0, side=1)  # adx_min=0 isolates the trend rule
    assert f(df, 200) is True


def test_gate_blocks_long_in_downtrend():
    df = _trend_df()
    df = df.iloc[::-1].reset_index(drop=True)
    df.index = pd.date_range("2024-01-01", periods=len(df), freq="4h")
    f = R.build_gate(df, adx_min=0.0, side=1)
    assert f(df, 200) is False


def test_gate_short_side_allows_in_downtrend():
    df = _trend_df()
    df = df.iloc[::-1].reset_index(drop=True)
    df.index = pd.date_range("2024-01-01", periods=len(df), freq="4h")
    f = R.build_gate(df, adx_min=0.0, side=-1)
    assert f(df, 200) is True


def test_gate_no_lookahead():
    """Decision at bar i must be identical whether or not future bars exist."""
    df = _trend_df(300)
    f_full = R.build_gate(df, adx_min=0.0, side=1)
    f_trunc = R.build_gate(df.iloc[:201], adx_min=0.0, side=1)
    assert f_full(df, 200) == f_trunc(df.iloc[:201], 200)


def test_gate_adx_min_blocks_weak_trend():
    """A very high adx_min blocks even a clean trend (ADX cannot reach it)."""
    df = _trend_df()
    f = R.build_gate(df, adx_min=999.0, side=1)
    assert f(df, 200) is False
