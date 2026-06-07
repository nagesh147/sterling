"""Mean-reversion sleeve scaffold — safety invariants.

This module is a DISABLED scaffold for the one real edge candidate. These tests
exist to stop it going live prematurely: it must stay disabled, out of the live
strategy set, and only "qualify" at the deflation bar (DSR >= 0.5).
"""
import numpy as np
import pandas as pd

from app.engines.edge.sleeves import mean_reversion as mr


def test_sleeve_is_disabled_by_default():
    assert mr.QUALIFIED is False


def test_qualification_requires_dsr_at_or_above_half():
    assert not mr.is_qualified(0.096)    # the real lead's actual best DSR
    assert not mr.is_qualified(0.4999)
    assert mr.is_qualified(0.5)
    assert mr.is_qualified(0.83)


def test_sleeve_not_wired_into_live_signal_fns():
    from app.engines.edge.strategies import SIGNAL_FNS
    # Until qualified, the scaffold must NOT appear in the live strategy set
    # that the scanners and edge feed iterate.
    assert not any("sleeve" in k for k in SIGNAL_FNS)


def test_signals_are_boolean_aligned_and_no_lookahead():
    n = 200
    close = pd.Series(np.linspace(120, 80, n) + np.sin(np.arange(n) / 5) * 3)
    df = pd.DataFrame({"open": close, "high": close + 1,
                       "low": close - 1, "close": close})
    s = mr.signals(df)
    assert s.dtype == bool and len(s) == n
    # Leading window before indicators warm up must be all-False (no peeking).
    assert not s[: mr.SLEEVE_PARAMS["bb_lookback"]].any()
