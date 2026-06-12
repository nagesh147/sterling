"""Kite instruments cache: parse, search, token resolution, TTL."""
import pytest

from app.services.exchanges.kite.instruments import InstrumentCache, parse_instruments_csv

_CSV = (
    "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,"
    "tick_size,lot_size,instrument_type,segment,exchange\n"
    "408065,1594,INFY,INFOSYS,1500.5,,0,0.05,1,EQ,NSE,NSE\n"
    "5633,22,ACC,ACC,2400,,0,0.05,1,EQ,NSE,NSE\n"
    "12345,48,NIFTY25JAN25000CE,NIFTY,120.5,2025-01-30,25000,0.05,50,CE,NFO-OPT,NFO\n"
)


def _cache(ttl=3600.0):
    calls = {"n": 0}

    async def fetch(exchange):
        calls["n"] += 1
        return _CSV

    c = InstrumentCache(fetch, ttl=ttl)
    return c, calls


def test_parse_coerces_numeric_columns():
    rows = parse_instruments_csv(_CSV)
    assert rows[0]["instrument_token"] == 408065
    assert rows[0]["strike"] == 0.0
    assert rows[2]["strike"] == 25000.0
    assert rows[2]["lot_size"] == 50


async def test_search_matches_symbol_and_name():
    c, _ = _cache()
    res = await c.search("INFY", exchange="NSE")
    assert any(r["tradingsymbol"] == "INFY" for r in res)
    by_name = await c.search("infosys", exchange="NSE")
    assert any(r["tradingsymbol"] == "INFY" for r in by_name)


async def test_resolve_token_exact():
    c, _ = _cache()
    assert await c.resolve_token("INFY", "NSE") == 408065
    with pytest.raises(KeyError):
        await c.resolve_token("NOPE", "NSE")


async def test_cache_hits_avoid_refetch_within_ttl():
    c, calls = _cache(ttl=3600.0)
    await c.load("NSE")
    await c.load("NSE")
    assert calls["n"] == 1  # second call served from cache


async def test_get_product_id_returns_token(monkeypatch):
    from app.services.exchanges.kite.client import KiteClient
    c = KiteClient(is_paper=True)

    async def fake_fetch(exchange):
        return _CSV
    c._instruments._fetch = fake_fetch
    assert await c.get_product_id("NSE:INFY") == 408065
    assert await c.get_product_id("NSE:NOPE") == 0  # graceful, never raises
