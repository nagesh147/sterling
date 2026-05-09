import pytest
from app.engines.risk.slippage import slippage_bps, effective_entry, size_after_slippage


def test_slippage_increases_with_leverage():
    assert slippage_bps(50, 500) > slippage_bps(1, 500)


def test_slippage_decreases_with_oi():
    assert slippage_bps(10, 2000) < slippage_bps(10, 100)


def test_effective_entry_long():
    price = 1000.0
    adj = effective_entry(price, direction=1, leverage=10, oi=None)
    assert adj > price  # long entry is worse (higher) due to slippage


def test_size_after_slippage_high_lev():
    base = 1.0
    reduced = size_after_slippage(base, leverage=50, oi=None)
    assert reduced < base
