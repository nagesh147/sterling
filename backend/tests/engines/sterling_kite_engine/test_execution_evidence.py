from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo
from types import SimpleNamespace
import pytest

from app.services.kite_engine.execution_evidence import entry_evidence

NOW = datetime(2026, 9, 7, 11, tzinfo=ZoneInfo("Asia/Kolkata"))


def client():
    row = dict(tradingsymbol="OPT", exchange="NFO", lot_size=50, tick_size=0.05,
               instrument_type="CE", expiry="2026-09-10")
    quote = dict(last_price=123.42, timestamp=NOW, last_trade_time=NOW)
    return SimpleNamespace(search_instruments=AsyncMock(return_value=[row]),
                           get_quote=AsyncMock(return_value={"NFO:OPT": quote}))


@pytest.mark.asyncio
async def test_tick_prices_respect_reserved_envelope():
    result = await entry_evidence(client(), "OPT", "NFO", 50, now=NOW)
    assert result.buy_limit == 123.75 and result.sell_limit == 123.05
    assert result.buy_limit <= result.last_price * 1.003


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("last_price", float("nan")),
    ("last_trade_time", NOW - timedelta(seconds=61)), ("timestamp", NOW + timedelta(seconds=1)),
    ("last_trade_time", None)])
async def test_invalid_or_stale_quote_blocks(field, value):
    c = client()
    c.get_quote.return_value["NFO:OPT"][field] = value
    with pytest.raises((ValueError, TypeError)):
        await entry_evidence(c, "OPT", "NFO", 50, now=NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("tick_size", 0), ("lot_size", 65),
    ("expiry", "2026-09-06"), ("exchange", "BFO"), ("instrument_type", "EQ")])
async def test_contract_metadata_must_match(field, value):
    c = client()
    c.search_instruments.return_value[0][field] = value
    with pytest.raises(ValueError):
        await entry_evidence(c, "OPT", "NFO", 50, now=NOW)
