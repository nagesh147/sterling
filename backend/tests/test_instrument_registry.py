from app.services.exchanges.instrument_registry import (
    get_instrument,
    has_options,
    is_supported,
    list_instruments,
)


def test_indian_index_registry():
    assert {item.underlying for item in list_instruments()} == {"NIFTY", "BANKNIFTY"}
    assert is_supported("nifty")
    assert is_supported("banknifty")
    assert has_options("NIFTY")


def test_unknown_instrument_fails_closed():
    assert get_instrument("UNKNOWN") is None
    assert not is_supported("UNKNOWN")
    assert not has_options("UNKNOWN")


def test_nifty_metadata_is_kite_inr():
    instrument = get_instrument("NIFTY")
    assert instrument is not None
    assert instrument.exchange == "zerodha"
    assert instrument.quote_currency == "INR"
    assert instrument.compatible_sources == ["zerodha"]
