import numpy as np
import pandas as pd
from app.engines.sterling_v2 import signals as S


def _df(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="4h")
    c = np.array(closes, float)
    o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c),
                         "low": np.minimum(o, c), "close": c, "volume": 1.0}, index=idx)


def test_short_ma_crossover_fires_on_bear_cross():
    closes = list(range(50, 30, -1))  # steady decline -> fast<slow eventually
    s = S.short_signal("ma_crossover", _df([60] * 25 + closes))
    assert s.sum() >= 1


def test_long_and_short_are_disjoint_definitions():
    df = _df([10, 12, 11, 13, 9, 8, 14])
    long = S.long_signal("ma_crossover", df)
    short = S.short_signal("ma_crossover", df)
    assert not np.any(long & short)  # a bar can't be both a fresh bull and bear cross


def test_short_breakout_fires_on_new_low():
    # 25 flat bars then a sharp break below the rolling 20-bar low
    s = S.short_signal("breakout", _df([100] * 25 + [80, 79, 78]))
    assert s.sum() >= 1


def test_all_short_fns_return_bool_arrays_of_right_length():
    df = _df(list(np.linspace(100, 80, 60)))
    for name in S.SHORT_FNS:
        arr = S.short_signal(name, df)
        assert arr.dtype == bool and arr.shape[0] == len(df)
