import pytest
from app.services.exchanges.instrument_registry import (
    get_instrument, list_instruments, is_supported, has_options,
)


class TestInstrumentRegistry:
    def test_btc_supported(self):
        assert is_supported("BTC")
        assert is_supported("btc")
    def test_nifty_supported(self):
        assert is_supported("NIFTY")
        assert is_supported("nifty")

    def test_eth_has_options(self):
        assert has_options("ETH")
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

    def test_list_includes_all(self):
        instruments = list_instruments()
        underlyings = {i.underlying for i in instruments}
        assert "BTC" in underlyings
        assert "ETH" in underlyings
        assert "SOL" in underlyings
        assert "NIFTY" in underlyings
        assert "BANKNIFTY" in underlyings

    def test_btc_metadata(self):
        inst = get_instrument("BTC")
        # Default exchange switched to Delta India for v4 (live trading target).
        assert inst.exchange == "delta_india"
        assert inst.perp_symbol == "BTC-PERPETUAL"
        assert inst.index_name == "btc_usd"
        assert inst.dvol_symbol == "BTC-DVOL"
        assert inst.preferred_dte_min == 10
        assert inst.preferred_dte_max == 15
        assert inst.min_dte == 5
        assert inst.force_exit_dte == 3

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
