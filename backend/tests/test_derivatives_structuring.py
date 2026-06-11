"""Derivatives structuring revamp — futures stop sanitization + delta options."""
from __future__ import annotations

import pytest

from app.engines.derivatives.selector import _futures_candidate, _sane_futures_stop
from app.engines.derivatives.profiles import get_profile
from app.engines.derivatives.schemas import MarketContext, SignalContext


def test_sane_stop_keeps_valid_stop():
    assert _sane_futures_stop("long", entry=100.0, stop=95.0, atr=2.0) == 95.0
    assert _sane_futures_stop("short", entry=100.0, stop=105.0, atr=2.0) == 105.0


def test_sane_stop_atr_fallback_when_stop_equals_entry():
    s = _sane_futures_stop("long", entry=100.0, stop=100.0, atr=2.0, k=1.5)
    assert s == pytest.approx(97.0)
    s = _sane_futures_stop("short", entry=100.0, stop=100.0, atr=2.0, k=1.5)
    assert s == pytest.approx(103.0)


def test_sane_stop_atr_fallback_when_wrong_side_or_missing():
    assert _sane_futures_stop("long", entry=100.0, stop=110.0, atr=2.0, k=1.5) == pytest.approx(97.0)
    assert _sane_futures_stop("short", entry=100.0, stop=None, atr=2.0, k=1.5) == pytest.approx(103.0)


def test_sane_stop_none_when_no_atr_and_bad_stop():
    assert _sane_futures_stop("long", entry=100.0, stop=100.0, atr=0.0) is None
    assert _sane_futures_stop("long", entry=100.0, stop=None, atr=0.0) is None


def _mkt(spot=62000.0):
    return MarketContext(spot=spot, underlying="BTC", funding_8h_pct=0.0001,
                         portfolio_value=500.0)


def _sig(direction="short", entry=62000.0, stop=62000.0, atr=600.0, tp=None):
    # stop==entry reproduces the collector's zero-distance fallback that DEFERed.
    return SignalContext(strategy="directional", underlying="BTC",
                         direction=direction, entry=entry, stop_loss=stop,
                         take_profit=tp, atr=atr, rr_target=2.0, signal_score=70.0,
                         signal_strength="SIGNAL", presized=False)


def test_futures_candidate_built_despite_zero_distance_stop():
    cand = _futures_candidate(signal=_sig(), market=_mkt(), profile=get_profile("directional"))
    assert cand is not None
    assert cand.instrument_type == "futures"
    assert cand.direction == "short"
    assert cand.stop_loss is not None and cand.stop_loss > cand.entry_price  # short stop above
    assert cand.contracts > 0


def test_futures_candidate_none_when_no_atr_and_bad_stop():
    cand = _futures_candidate(signal=_sig(atr=0.0), market=_mkt(),
                              profile=get_profile("directional"))
    assert cand is None
