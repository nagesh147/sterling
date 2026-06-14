from app.services.kite_engine.universe import UniverseItem, build_universe


def test_build_universe_from_instruments_dump():
    # NFO option instruments → their underlyings become the equity universe
    nfo = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000CE", "instrument_type": "CE"},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE25JUN3000PE", "instrument_type": "PE"},
        {"name": "INFY", "tradingsymbol": "INFY25JUN1500CE", "instrument_type": "CE"},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN22000CE", "instrument_type": "CE"},
    ]
    equities = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 111, "exchange": "NSE"},
        {"tradingsymbol": "INFY", "instrument_token": 222, "exchange": "NSE"},
        {"tradingsymbol": "NIFTY 50", "instrument_token": 256265, "exchange": "NSE"},
        {"tradingsymbol": "SENSEX", "instrument_token": 265, "exchange": "BSE"},
    ]
    uni = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=equities)
    names = {u.name for u in uni}
    assert "RELIANCE" in names and "INFY" in names
    # indices always present
    assert "NIFTY 50" in names

    r = next(u for u in uni if u.name == "RELIANCE")
    assert isinstance(r, UniverseItem)
    assert r.token == 111 and r.option_exchange == "NFO" and r.tradingsymbol == "RELIANCE"

    nifty = next(u for u in uni if u.name == "NIFTY 50")
    # index: spot token resolved from spot_symbol, option chain filters by option_name
    assert nifty.is_index and nifty.token == 256265 and nifty.tradingsymbol == "NIFTY"


def test_indices_resolve_from_spot_token_without_dump():
    # the bug: indices were dropped when their spot row wasn't in the equities dump.
    # With spot_token in config, every index keeps a candle-fetch token.
    uni = build_universe(nfo_instruments=[], bfo_instruments=[], equities=[])
    idx = {u.name: u for u in uni if u.is_index}
    assert idx["NIFTY 50"].token == 256265
    assert idx["NIFTY BANK"].token == 260105
    assert idx["NIFTY FIN SERVICE"].token == 257801
    assert idx["SENSEX"].token == 265 and idx["SENSEX"].option_exchange == "BFO"
    # all four indices present with non-zero tokens (none skipped downstream)
    assert all(u.token > 0 for u in idx.values()) and len(idx) == 4


def test_equity_without_spot_listing_is_skipped():
    # an option underlying with no resolvable spot token is dropped (can't fetch candles)
    nfo = [{"name": "GHOSTCO", "tradingsymbol": "GHOSTCO25JUN100CE", "instrument_type": "CE"}]
    uni = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=[])
    assert all(u.name != "GHOSTCO" for u in uni)


def test_option_rows_deduped_per_underlying():
    nfo = [
        {"name": "TCS", "tradingsymbol": "TCS25JUN3900CE", "instrument_type": "CE"},
        {"name": "TCS", "tradingsymbol": "TCS25JUN3900PE", "instrument_type": "PE"},
        {"name": "TCS", "tradingsymbol": "TCS25JUL3900CE", "instrument_type": "CE"},
    ]
    equities = [{"tradingsymbol": "TCS", "instrument_token": 999, "exchange": "NSE"}]
    uni = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=equities)
    assert sum(1 for u in uni if u.name == "TCS") == 1
