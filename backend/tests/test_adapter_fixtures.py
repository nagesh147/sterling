"""
Fixture-based adapter tests using sanitized real-shaped API responses.

Tests that the Deribit and OKX adapters correctly parse actual response
shapes from the live APIs, without making any network calls.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.exchanges.adapters.deribit import DeribitAdapter
from app.services.exchanges.adapters.okx import OKXAdapter
from app.services.exchanges import instrument_registry as registry


# ── Fixtures (sanitized real-shaped responses) ──────────────────────────────

# Deribit: _get() strips the "result" wrapper, so fixtures are the inner payload.

DERIBIT_CANDLES_RESULT = {
    "ticks":  [1714000000000, 1714003600000, 1714007200000],
    "open":   [62100.0, 62200.0, 62050.0],
    "high":   [62300.0, 62400.0, 62300.0],
    "low":    [61900.0, 62000.0, 61800.0],
    "close":  [62200.0, 62050.0, 62250.0],
    "volume": [120.5, 98.3, 145.2],
    "status": "ok",
}

DERIBIT_INDEX_RESULT = {
    "index_price": 62180.5,
    "estimated_delivery_price": 62180.5,
}

DERIBIT_DVOL_RESULT = {
    "data": [
        [1714000000000, 72.1, 73.0, 71.5, 72.4],
        [1714086400000, 73.2, 74.1, 72.8, 73.5],
        [1714172800000, 75.0, 76.2, 74.5, 75.8],
    ]
}

# Deribit option chain returns a list directly after stripping "result".
# Use far-future expiry (27DEC26) so DTE > 0 regardless of test date.
DERIBIT_OPTION_CHAIN_RESULT = [
    {
        "instrument_name": "BTC-27DEC26-65000-C",
        "underlying_index": "BTC-27DEC26",
        "underlying_price": 62180.0,
        "bid_price": 0.052, "ask_price": 0.055,
        "mark_price": 0.0535,
        "mid_price": 0.0535,
        "mark_iv": 72.5,
        "delta": 0.38,
        "open_interest": 250.0,
        "volume": 18.5,
        "creation_timestamp": 1714000000000,
        "last_updated": 1714000001000,
    },
    {
        "instrument_name": "BTC-27DEC26-60000-P",
        "underlying_index": "BTC-27DEC26",
        "underlying_price": 62180.0,
        "bid_price": 0.031, "ask_price": 0.033,
        "mark_price": 0.032,
        "mid_price": 0.032,
        "mark_iv": 68.2,
        "delta": -0.28,
        "open_interest": 180.0,
        "volume": 12.1,
        "creation_timestamp": 1714000000000,
        "last_updated": 1714000001000,
    },
]

OKX_CANDLES_RESPONSE = {
    "code": "0",
    "data": [
        # newest first: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        ["1714007200000", "62250.0", "62300.0", "61800.0", "62250.0", "145.2", "0", "0", "1"],
        ["1714003600000", "62200.0", "62400.0", "62000.0", "62050.0", "98.3",  "0", "0", "1"],
        ["1714000000000", "62100.0", "62300.0", "61900.0", "62200.0", "120.5", "0", "0", "1"],
    ]
}

OKX_INDEX_RESPONSE = {
    "code": "0",
    "data": [{"instId": "BTC-USDT", "idxPx": "62180.5", "ts": "1714000000000"}]
}

# OKX: use far-future expiry (261231 = Dec 31, 2026) so DTE > 0.
OKX_OPT_SUMMARY_RESPONSE = {
    "code": "0",
    "data": [
        {
            "instId": "BTC-USD-261231-65000-C",
            "markVol": "0.7250",
            "realVol": "0.6980",
            "delta": "0.3800",
            "markPx": "0.0535",
            "fwdPx": "0.0535",
            "oi": "250",
            "oiUsd": "15500000",
            "ts": "1714000000000",
        },
        {
            "instId": "BTC-USD-261231-60000-P",
            "markVol": "0.6820",
            "realVol": "0.6500",
            "delta": "-0.2800",
            "markPx": "0.0320",
            "fwdPx": "0.0320",
            "oi": "180",
            "oiUsd": "11160000",
            "ts": "1714000000000",
        },
    ]
}

OKX_TICKERS_OPTION_RESPONSE = {
    "code": "0",
    "data": [
        {
            "instId": "BTC-USD-261231-65000-C",
            "instType": "OPTION",
            "bidPx": "0.052",
            "askPx": "0.055",
            "last": "0.0535",
            "vol24h": "18.5",
            "ts": "1714000000000",
        },
        {
            "instId": "BTC-USD-261231-60000-P",
            "instType": "OPTION",
            "bidPx": "0.031",
            "askPx": "0.033",
            "last": "0.032",
            "vol24h": "12.1",
            "ts": "1714000000000",
        },
    ]
}


# ── Deribit adapter tests ────────────────────────────────────────────────────

@pytest.fixture
def deribit():
    return DeribitAdapter()


@pytest.fixture
def btc_inst():
    return registry.get_instrument("BTC")


@pytest.mark.asyncio
async def test_deribit_get_candles_parse(deribit, btc_inst):
    async def _fake_get(path, params):
        return DERIBIT_CANDLES_RESULT

    with patch.object(deribit, "_get", side_effect=_fake_get):
        candles = await deribit.get_candles(btc_inst, "1H", limit=10)

    assert len(candles) == 3
    # Deribit returns chronological order
    assert candles[0].close == 62200.0
    assert candles[1].close == 62050.0
    assert candles[2].close == 62250.0
    for c in candles:
        assert c.high >= c.low
        assert c.volume > 0


@pytest.mark.asyncio
async def test_deribit_get_index_price(deribit, btc_inst):
    async def _fake_get(path, params):
        return DERIBIT_INDEX_RESULT

    with patch.object(deribit, "_get", side_effect=_fake_get):
        price = await deribit.get_index_price(btc_inst)

    assert price == pytest.approx(62180.5, rel=1e-3)


@pytest.mark.asyncio
async def test_deribit_get_dvol(deribit, btc_inst):
    async def _fake_get(path, params):
        return DERIBIT_DVOL_RESULT

    with patch.object(deribit, "_get", side_effect=_fake_get):
        dvol = await deribit.get_dvol(btc_inst)

    assert dvol is not None
    assert 70.0 < dvol < 80.0


@pytest.mark.asyncio
async def test_deribit_get_dvol_history(deribit, btc_inst):
    async def _fake_get(path, params):
        return DERIBIT_DVOL_RESULT

    with patch.object(deribit, "_get", side_effect=_fake_get):
        hist = await deribit.get_dvol_history(btc_inst, days=3)

    assert len(hist) == 3
    assert all(70.0 < v < 80.0 for v in hist)


@pytest.mark.asyncio
async def test_deribit_option_chain_parse(deribit, btc_inst):
    async def _fake_get(path, params):
        return DERIBIT_OPTION_CHAIN_RESULT

    with patch.object(deribit, "_get", side_effect=_fake_get):
        chain = await deribit.get_option_chain(btc_inst)

    assert len(chain) == 2
    calls = [o for o in chain if o.option_type == "call"]
    puts  = [o for o in chain if o.option_type == "put"]
    assert len(calls) == 1 and len(puts) == 1

    c = calls[0]
    assert c.strike == 65000.0
    assert c.bid == pytest.approx(0.052, rel=0.01)   # stored as raw BTC-denominated price
    assert c.mark_iv == pytest.approx(72.5, rel=0.01)
    assert c.open_interest == pytest.approx(250.0, rel=0.01)


# ── OKX adapter tests ────────────────────────────────────────────────────────

@pytest.fixture
def okx():
    return OKXAdapter()


@pytest.mark.asyncio
async def test_okx_get_candles_parse(okx, btc_inst):
    async def _fake_get(path, params):
        return OKX_CANDLES_RESPONSE["data"]

    with patch.object(okx, "_get", side_effect=_fake_get):
        candles = await okx.get_candles(btc_inst, "1H", limit=10)

    # OKX returns newest-first; adapter reverses to chronological
    assert len(candles) == 3
    assert candles[0].close == 62200.0   # oldest
    assert candles[2].close == 62250.0   # newest
    for c in candles:
        assert c.volume > 0


@pytest.mark.asyncio
async def test_okx_get_index_price(okx, btc_inst):
    async def _fake_get(path, params):
        return OKX_INDEX_RESPONSE["data"]

    with patch.object(okx, "_get", side_effect=_fake_get):
        price = await okx.get_index_price(btc_inst)

    assert price == pytest.approx(62180.5, rel=1e-3)


@pytest.mark.asyncio
async def test_okx_get_dvol_via_atm_iv(okx, btc_inst):
    """OKX get_dvol returns ATM option markVol from opt-summary."""
    async def _fake_get(path, params):
        if "opt-summary" in path:
            return OKX_OPT_SUMMARY_RESPONSE["data"]
        return OKX_INDEX_RESPONSE["data"]

    # _get_atm_iv also calls get_index_price which uses _get internally
    with patch.object(okx, "_get", side_effect=_fake_get):
        dvol = await okx.get_dvol(btc_inst)

    assert dvol is not None
    # markVol in fixture is "0.7250" — that's the raw value from OKX
    assert 0.6 < dvol < 0.8, f"Expected markVol in [0.6, 0.8], got {dvol}"


@pytest.mark.asyncio
async def test_okx_get_dvol_history_returns_hv_series(okx, btc_inst):
    """OKX dvol_history returns synthetic HV from 1H candles — should be a non-empty list."""
    # Build enough fake candles
    from app.schemas.market import Candle
    fake_candles = [
        Candle(
            timestamp_ms=1_714_000_000_000 + i * 3_600_000,
            open=62000.0 + i, high=62100.0 + i, low=61900.0 + i,
            close=62000.0 + i * 0.5, volume=100.0,
        )
        for i in range(32 * 24 + 1)
    ]

    with patch.object(okx, "get_candles", return_value=fake_candles):
        hist = await okx.get_dvol_history(btc_inst, days=30)

    assert isinstance(hist, list)
    assert len(hist) > 0
    assert all(isinstance(v, float) and v >= 0 for v in hist)


@pytest.mark.asyncio
async def test_okx_option_chain_parse(okx, btc_inst):
    async def _fake_get(path, params):
        if "opt-summary" in path:
            return OKX_OPT_SUMMARY_RESPONSE["data"]
        if "market/tickers" in path:
            return OKX_TICKERS_OPTION_RESPONSE["data"]
        return []

    with patch.object(okx, "_get", side_effect=_fake_get):
        chain = await okx.get_option_chain(btc_inst)

    assert len(chain) == 2
    calls = [o for o in chain if o.option_type == "call"]
    puts  = [o for o in chain if o.option_type == "put"]
    assert len(calls) == 1 and len(puts) == 1
    c = calls[0]
    assert c.strike == 65000.0
    assert c.mark_iv == pytest.approx(0.725, rel=0.01)
    assert c.delta == pytest.approx(0.38, rel=0.01)


@pytest.mark.asyncio
async def test_okx_option_chain_bad_instid_skipped(okx, btc_inst):
    """Malformed instIds should be silently skipped."""
    bad_data = [
        {"instId": "NOT-VALID", "bidPx": "0.05", "askPx": "0.06", "last": "0.055",
         "vol24h": "10", "ts": "1714000000000"},
    ]

    async def _fake_get(path, params):
        if "market/tickers" in path:
            return bad_data
        return []

    with patch.object(okx, "_get", side_effect=_fake_get):
        chain = await okx.get_option_chain(btc_inst)

    assert chain == []


@pytest.mark.asyncio
async def test_deribit_ping_returns_true(deribit):
    async def _fake_get(path, params):
        return {"result": {"timestamp": 1714000000000}}

    with patch.object(deribit, "_get", side_effect=_fake_get):
        result = await deribit.ping()

    assert result is True


@pytest.mark.asyncio
async def test_okx_ping_returns_true(okx):
    async def _fake_get(path, params):
        return [{"ts": "1714000000000"}]

    with patch.object(okx, "_get", side_effect=_fake_get):
        result = await okx.ping()

    assert result is True


@pytest.mark.asyncio
async def test_adapter_ping_returns_false_on_error(deribit, okx):
    async def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    with patch.object(deribit, "_get", side_effect=_raise):
        assert await deribit.ping() is False

    with patch.object(okx, "_get", side_effect=_raise):
        assert await okx.ping() is False
