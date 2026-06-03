import numpy as np
import pandas as pd
from app.engines.sterling_v2 import portfolio as P


def test_inverse_vol_gives_more_weight_to_calmer_book():
    rng = np.random.default_rng(0)
    calm = rng.normal(0.0, 0.001, 50)   # low (nonzero) vol
    wild = rng.normal(0.0, 0.05, 50)    # high vol
    w = P.inverse_vol_weights({"calm": calm, "wild": wild})
    assert w["calm"] > w["wild"]
    assert abs(sum(w.values()) - 1.0) < 1e-9


def test_correlation_penalty_favors_the_diversifier():
    rng = np.random.default_rng(1)
    base = rng.normal(0, 0.02, 200)
    a = base + rng.normal(0, 1e-4, 200)   # a, b nearly identical (corr ~1)
    b = base + rng.normal(0, 1e-4, 200)
    c = rng.normal(0, 0.02, 200)          # c independent, same vol
    books = {"a": a, "b": b, "c": c}
    inv = P.inverse_vol_weights(books)
    pen = P.correlation_penalized_weights(books, lam=1.0)
    # under pure inverse-vol all three are ~equal; the penalty must lift the
    # diversifier c above the correlated pair a/b.
    assert pen["c"] > pen["a"] and pen["c"] > inv["c"]
    assert abs(sum(pen.values()) - 1.0) < 1e-9


def test_dd_breaker_flattens_after_threshold():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    crash = pd.Series([1.0, 0.9, 0.7, 0.9, 1.1], index=idx)  # -30% then recover
    eq = P.combine_equity({"a": crash}, {"a": 1.0}, dd_halt=0.20)
    # after the -30% breach the curve is frozen, so it must NOT recover to 1.1
    assert eq.iloc[-1] < 1.0
    assert abs(eq.iloc[-1] - 0.7) < 1e-9  # frozen at the breach level


def test_combine_no_halt_when_within_threshold():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    rise = pd.Series([1.0, 1.02, 1.05, 1.04, 1.08], index=idx)  # max DD ~ -1%
    eq = P.combine_equity({"a": rise}, {"a": 1.0}, dd_halt=0.20)
    assert eq.iloc[-1] > 1.0  # never halted; rides the gains
