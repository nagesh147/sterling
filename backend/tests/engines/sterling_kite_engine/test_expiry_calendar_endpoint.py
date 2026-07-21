from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from app.api.v1.endpoints import kite_engine


@pytest.mark.asyncio
async def test_expiry_calendar_endpoint_reads_cached_nfo_and_bfo_dumps(monkeypatch):
    client = SimpleNamespace(search_instruments=AsyncMock(side_effect=[
        [
            {
                "name": "NIFTY", "tradingsymbol": "NIFTY99JAN25000CE",
                "instrument_type": "CE", "expiry": "2099-01-27",
            },
            {
                "name": "RELIANCE", "tradingsymbol": "RELIANCE99JAN2500CE",
                "instrument_type": "CE", "expiry": "2099-01-27",
            },
        ],
        [],
    ]))
    monkeypatch.setattr(kite_engine, "_client", AsyncMock(return_value=client))
    monkeypatch.setattr(kite_engine, "load_universe_config", lambda: {
        "indices": [
            {"name": "NIFTY 50", "option_name": "NIFTY", "option_exchange": "NFO"},
        ],
    })
    monkeypatch.setattr(kite_engine, "CURATED_STOCK_NAMES", ["RELIANCE"])

    result = await kite_engine.expiry_calendar(SimpleNamespace(user_id="trader"))

    assert client.search_instruments.await_args_list == [
        call("", "NFO", limit=1_000_000),
        call("", "BFO", limit=1_000_000),
    ]
    assert result["source"] == "kite_instruments"
    assert result["indices"][0]["monthly"] == ["2099-01-27"]
    assert result["stocks"][0]["monthly"] == ["2099-01-27"]
