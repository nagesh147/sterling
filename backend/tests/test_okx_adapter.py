"""
OKX adapter tests — all external HTTP mocked.
"""
import time
import pytest
from unittest.mock import AsyncMock
from app.services.exchanges.adapters.okx import (
    OKXAdapter, _normalize_ts_ms, _okx_dte, _okx_option_type, _okx_strike,
)
from app.services.exchanges.instrument_registry import get_instrument

_BTC = get_instrument("BTC")
_ETH = get_instrument("ETH")
_SOL = get_instrument("SOL")  # no OKX underlying for options


class TestOKXHelpers:
    def test_dte_future(self):
        dte = _okx_dte("351231")  # year 35 = 2035 (Python %y: 00-68 → 2000-2068)
        assert dte > 0

    def test_dte_invalid(self):
        assert _okx_dte("INVALID") == -1

    def test_option_type_call(self):
        assert _okx_option_type("BTC-USD-241227-100000-C") == "call"

    def test_option_type_put(self):
        assert _okx_option_type("BTC-USD-241227-100000-P") == "put"

    def test_strike_parsed(self):
        assert _okx_strike("BTC-USD-241227-100000-C") == 100000.0

    def test_strike_invalid(self):
        assert _okx_strike("BAD") is None

    def test_ts_ms_normalization(self):
        ts_ms = 1_700_000_000_000
        assert _normalize_ts_ms(ts_ms) == ts_ms
        assert _normalize_ts_ms(1_700_000_000) == ts_ms  # seconds


def _make_adapter() -> OKXAdapter:
    return OKXAdapter(base_url="https://mock.okx.test")


class TestOKXAdapterMocked:
    @pytest.mark.asyncio
    async def test_ping_success(self):
        adapter = _make_adapter()
        adapter._get = AsyncMock(return_value=[{"ts": str(int(time.time() * 1000))}])
        assert await adapter.ping()

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        adapter = _make_adapter()
        adapter._get = AsyncMock(side_effect=Exception("network"))
        assert not await adapter.ping()

    @pytest.mark.asyncio
    async def test_get_index_price(self):
        adapter = _make_adapter()
        adapter._get = AsyncMock(return_value=[{"idxPx": "42000.5"}])
        price = await adapter.get_index_price(_BTC)
        assert price == pytest.approx(42000.5)

    @pytest.mark.asyncio
    async def test_get_perp_price(self):
        adapter = _make_adapter()
        adapter._get = AsyncMock(return_value=[{"last": "42100.0"}])
        price = await adapter.get_perp_price(_BTC)
        assert price == pytest.approx(42100.0)

    @pytest.mark.asyncio
    async def test_get_candles_parses_and_reverses(self):
        now_ms = int(time.time() * 1000)
        # OKX returns newest first
        adapter = _make_adapter()
        adapter._get = AsyncMock(return_value=[
            [str(now_ms), "42100", "42200", "42000", "42150", "50", "50", "50", "1"],
            [str(now_ms - 3_600_000), "41900", "42000", "41800", "42000", "40", "40", "40", "1"],
        ])
        candles = await adapter.get_candles(_BTC, "1H", limit=2)
        assert len(candles) == 2
        # After reversal, older bar comes first
        assert candles[0].timestamp_ms < candles[1].timestamp_ms
        assert candles[1].close == pytest.approx(42150.0)

    @pytest.mark.asyncio
    async def test_option_chain_empty_when_no_okx_underlying(self):
        adapter = _make_adapter()
        # SOL has no okx_underlying
        chain = await adapter.get_option_chain(_SOL)
        assert chain == []

    @pytest.mark.asyncio
    async def test_option_chain_parses_tickers(self):
        adapter = _make_adapter()
        now_ms = int(time.time() * 1000)

        async def fake_get(path, params):
            if "opt-summary" in path:
                return [{"instId": "BTC-USD-991231-100000-C", "markVol": "55.0", "delta": "0.45", "fwdPx": "500.0"}]
            return [
                {
                    "instId": "BTC-USD-991231-100000-C",
                    "bidPx": "490.0", "askPx": "510.0",
                    "last": "500.0", "vol24h": "20.0", "ts": str(now_ms),
                }
            ]

        adapter._get = fake_get
        chain = await adapter.get_option_chain(_BTC)
        assert len(chain) == 1
        opt = chain[0]
        assert opt.option_type == "call"
        assert opt.strike == 100000.0
        assert opt.bid == pytest.approx(490.0)
        assert opt.mark_iv == pytest.approx(55.0)

    @pytest.mark.asyncio
    async def test_dvol_returns_none(self):
        adapter = _make_adapter()
        result = await adapter.get_dvol(_BTC)
        assert result is None

    @pytest.mark.asyncio
    async def test_dvol_history_empty(self):
        adapter = _make_adapter()
        result = await adapter.get_dvol_history(_BTC)
        assert result == []

    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        adapter = _make_adapter()
        # Trigger client creation
        adapter._client = None
        await adapter.close()  # should not raise even with no client
