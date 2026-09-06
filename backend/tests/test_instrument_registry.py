import pytest
from app.services.exchanges.instrument_registry import (
    get_instrument, list_instruments, is_supported, has_options,
)


class TestInstrumentRegistry:
    def test_nifty_supported(self):
        assert is_supported("NIFTY")
        assert is_supported("nifty")

    def test_banknifty_supported(self):
        assert is_supported("BANKNIFTY")
        assert is_supported("banknifty")

    def test_xrp_no_options(self):
        assert not has_options("XRP")
    def test_nifty_has_options(self):
        assert has_options("NIFTY")

    def test_banknifty_has_options(self):
        assert has_options("BANKNIFTY")

    def test_unknown_returns_none(self):
        assert get_instrument("DOGE") is None
        assert not is_supported("DOGE")
        assert not has_options("DOGE")
        assert get_instrument("BTC") is None
        assert not is_supported("BTC")
        assert not has_options("BTC")

    def test_sol_no_dvol(self):
        inst = get_instrument("SOL")
    def test_nifty_metadata(self):
        inst = get_instrument("NIFTY")
        assert inst.exchange == "zerodha"
        assert inst.quote_currency == "INR"
        assert inst.exchange_currency == "INR"
        assert inst.contract_multiplier == 50.0
        assert inst.strike_step == 50.0
        assert inst.has_options is True
        assert inst.dvol_symbol is None
