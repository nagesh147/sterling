from app.services.kite_engine.universe import (
    UniverseItem,
    build_universe,
    select_scan_universe,
)


def test_select_scan_universe_granular_and_high_liquidity_only():
    ix1 = UniverseItem("NIFTY 50", "NIFTY", 1, "INDICES", "NFO", is_index=True)
    ix2 = UniverseItem("SENSEX", "SENSEX", 2, "INDICES", "BFO", is_index=True)
    s1 = UniverseItem("RELIANCE", "RELIANCE", 3, "NSE", "NFO")
    s2 = UniverseItem("INFY", "INFY", 4, "NSE", "NFO")
    thin = UniverseItem("GHOSTCO", "GHOSTCO", 5, "NSE", "NFO")
    universe = [ix1, ix2, s1, s2, thin]

    assert select_scan_universe(
        universe, indices=["NIFTY 50"], stocks=["RELIANCE"], all_stocks=False
    ) == [ix1, s1]
    assert select_scan_universe(
        universe, indices=["NIFTY 50", "SENSEX"], stocks=[], all_stocks=True
    ) == [ix1, ix2, s1, s2]
    assert select_scan_universe(
        universe, indices=[], stocks=["INFY", "GHOSTCO"], all_stocks=False
    ) == [s2]


def test_build_universe_from_instruments_dump():
    nfo = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000CE", "instrument_type": "CE"},
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000PE", "instrument_type": "PE"},
        {"name": "INFY", "tradingsymbol": "INFY26JUN1500CE", "instrument_type": "CE"},
        {"name": "NIFTY", "tradingsymbol": "NIFTY26JUN22000CE", "instrument_type": "CE"},
    ]
    equities = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 111, "exchange": "NSE"},
        {"tradingsymbol": "INFY", "instrument_token": 222, "exchange": "NSE"},
        {"tradingsymbol": "NIFTY 50", "instrument_token": 256265, "exchange": "NSE"},
        {"tradingsymbol": "SENSEX", "instrument_token": 265, "exchange": "BSE"},
    ]
    universe = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=equities)
    names = {item.name for item in universe}
    assert {"RELIANCE", "INFY", "NIFTY 50"} <= names

    reliance = next(item for item in universe if item.name == "RELIANCE")
    assert reliance.token == 111
    assert reliance.option_exchange == "NFO"
    assert reliance.tradingsymbol == "RELIANCE"

    nifty = next(item for item in universe if item.name == "NIFTY 50")
    assert nifty.is_index
    assert nifty.token == 256265
    assert nifty.tradingsymbol == "NIFTY"


def test_build_universe_rejects_non_high_liquidity_fno_names():
    nfo = [
        {"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000CE", "instrument_type": "CE"},
        {"name": "TATASTEEL", "tradingsymbol": "TATASTEEL26JUN200CE", "instrument_type": "CE"},
        {"name": "GHOSTCO", "tradingsymbol": "GHOSTCO26JUN100CE", "instrument_type": "CE"},
    ]
    equities = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 1, "exchange": "NSE"},
        {"tradingsymbol": "TATASTEEL", "instrument_token": 2, "exchange": "NSE"},
        {"tradingsymbol": "GHOSTCO", "instrument_token": 3, "exchange": "NSE"},
    ]
    universe = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=equities)
    stock_names = {item.name for item in universe if not item.is_index}
    assert stock_names == {"RELIANCE"}


def test_indices_resolve_from_spot_token_without_dump():
    universe = build_universe(nfo_instruments=[], bfo_instruments=[], equities=[])
    indices = {item.name: item for item in universe if item.is_index}
    assert indices["NIFTY 50"].token == 256265
    assert indices["NIFTY BANK"].token == 260105
    assert indices["NIFTY FIN SERVICE"].token == 257801
    assert indices["SENSEX"].token == 265
    assert indices["SENSEX"].option_exchange == "BFO"
    assert all(item.token > 0 for item in indices.values())
    assert len(indices) == 4


def test_equity_without_spot_listing_is_skipped():
    nfo = [{"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000CE", "instrument_type": "CE"}]
    universe = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=[])
    assert all(item.name != "RELIANCE" for item in universe)


def test_dual_listed_fno_stock_prefers_nse_spot_token():
    nfo = [{"name": "RELIANCE", "tradingsymbol": "RELIANCE26JUN3000CE", "instrument_type": "CE"}]
    equities = [
        {"tradingsymbol": "RELIANCE", "instrument_token": 738561, "exchange": "NSE"},
        {"tradingsymbol": "RELIANCE", "instrument_token": 128083204, "exchange": "BSE"},
    ]
    universe = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=equities)
    reliance = next(item for item in universe if item.name == "RELIANCE")
    assert reliance.exchange == "NSE"
    assert reliance.token == 738561


def test_option_rows_deduped_per_underlying():
    nfo = [
        {"name": "TCS", "tradingsymbol": "TCS26JUN3900CE", "instrument_type": "CE"},
        {"name": "TCS", "tradingsymbol": "TCS26JUN3900PE", "instrument_type": "PE"},
        {"name": "TCS", "tradingsymbol": "TCS26JUL3900CE", "instrument_type": "CE"},
    ]
    equities = [{"tradingsymbol": "TCS", "instrument_token": 999, "exchange": "NSE"}]
    universe = build_universe(nfo_instruments=nfo, bfo_instruments=[], equities=equities)
    assert sum(1 for item in universe if item.name == "TCS") == 1
