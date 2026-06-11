"""Derivatives structuring revamp — futures stop sanitization + delta options."""
from __future__ import annotations

import pytest

from app.engines.derivatives.selector import _sane_futures_stop


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
