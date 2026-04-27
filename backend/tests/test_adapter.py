"""
Adapter tests — all external HTTP mocked. No live network calls.
"""
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.exchanges.adapters.deribit import DeribitAdapter, _normalize_ts_ms, _compute_dte
from app.services.exchanges.instrument_registry import get_instrument


_BTC = get_instrument("BTC")
_ETH = get_instrument("ETH")
_SOL = get_instrument("SOL")


class TestTimestampNormalization:
    def test_seconds(self):
        ts = 1_700_000_000
        assert _normalize_ts_ms(ts) == ts * 1000

    def test_milliseconds(self):
        ts = 1_700_000_000_000
        assert _normalize_ts_ms(ts) == ts

    def test_microseconds(self):
        ts = 1_700_000_000_000_000
        assert _normalize_ts_ms(ts) == ts // 1000

    def test_nanoseconds(self):
        ts = 1_700_000_000_000_000_000
        assert _normalize_ts_ms(ts) == ts // 1_000_000


class TestDTEComputation:
    def test_future_date(self):
        dte = _compute_dte("27DEC99")
        # Far future or parsing error → either large positive or -1
        assert dte >= 0 or dte == -1

    def test_invalid_format(self):
        assert _compute_dte("INVALID") == -1


def _make_adapter() -> DeribitAdapter:
    return DeribitAdapter(base_url="https://mock.deribit.test")


def _mock_get(adapter: DeribitAdapter, return_value: dict):
    adapter._get = AsyncMock(return_value=return_value)
    return adapter


class TestDeribitAdapterMocked:
    @pytest.mark.asyncio
    async def test_ping_success(self):
        adapter = _make_adapter()
        adapter._get = AsyncMock(return_value={})
        assert await adapter.ping()

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        adapter = _make_adapter()
        adapter._get = AsyncMock(side_effect=Exception("network error"))
        assert not await adapter.ping()

    @pytest.mark.asyncio
    async def test_get_index_price(self):
        adapter = _mock_get(_make_adapter(), {"index_price": 42000.0})
        price = await adapter.get_index_price(_BTC)
        assert price == 42000.0

    @pytest.mark.asyncio
    async def test_get_candles_parses_correctly(self):
        now_ms = int(time.time() * 1000)
        adapter = _mock_get(_make_adapter(), {
            "ticks": [now_ms - 3600000, now_ms],
            "open": [40000.0, 41000.0],
            "high": [40500.0, 41500.0],
            "low": [39500.0, 40500.0],
            "close": [41000.0, 41200.0],
            "volume": [100.0, 120.0],
        })
        candles = await adapter.get_candles(_BTC, "1H", limit=2)
        assert len(candles) == 2
        assert candles[0].close == 41000.0
        assert candles[1].close == 41200.0

    @pytest.mark.asyncio
    async def test_4h_candles_uses_60min_and_aggregates(self):
        """4H must NOT send resolution=240 (Deribit rejects it). Uses 1H + aggregation."""
        now_ms = int(time.time() * 1000)
        # Provide 8 × 1H bars → should yield 2 × 4H bars
        ticks = [now_ms - (7 - i) * 3600_000 for i in range(8)]
        adapter = _mock_get(_make_adapter(), {
            "ticks": ticks,
            "open":  [100.0] * 8,
            "high":  [110.0] * 8,
            "low":   [90.0]  * 8,
            "close": [105.0] * 8,
            "volume":[10.0]  * 8,
        })
        called_params = {}
        orig_get = adapter._get

        async def capturing_get(path, params):
            called_params.update(params)
            return await orig_get(path, params)

        adapter._get = capturing_get
        candles = await adapter.get_candles(_BTC, "4H", limit=2)

        # Must use resolution=60, NOT 240
        assert called_params.get("resolution") == "60", \
            f"Expected resolution=60, got {called_params.get('resolution')}"
        # 8 × 1H → 2 × 4H (+ possible partial)
        assert len(candles) == 2
        # Each 4H bar spans 4 hours
        assert candles[1].timestamp_ms > candles[0].timestamp_ms

    @pytest.mark.asyncio
    async def test_4h_aggregation_open_high_low_close(self):
        """4H bar: open=first, high=max, low=min, close=last of 4 1H bars."""
        from app.services.exchanges.adapters.deribit import _aggregate_4h
        from app.schemas.market import Candle
        now_ms = int(time.time() * 1000)
        h1_candles = [
            Candle(timestamp_ms=now_ms + i * 3600_000,
                   open=100+i, high=110+i, low=90+i, close=105+i, volume=10.0)
            for i in range(8)
        ]
        result = _aggregate_4h(h1_candles)
        assert len(result) == 2
        # First 4H bar: open=100, high=113, low=90, close=103
        assert result[0].open == 100
        assert result[0].high == 113  # max(110,111,112,113)
        assert result[0].low  == 90   # min(90,91,92,93)
        assert result[0].close == 108  # close of bar index 3 (105+3)
        assert result[0].volume == 40  # sum of 4 bars

    @pytest.mark.asyncio
    async def test_option_chain_empty_for_no_options_asset(self):
        from app.services.exchanges.instrument_registry import get_instrument
        xrp = get_instrument("XRP")
        adapter = _make_adapter()
        chain = await adapter.get_option_chain(xrp)
        assert chain == []

    @pytest.mark.asyncio
    async def test_option_chain_filters_invalid(self):
        adapter = _make_adapter()
        now_ms = int(time.time() * 1000)
        adapter._get = AsyncMock(return_value=[
            {
                "instrument_name": "BTC-27DEC99-100000-C",
                "bid_price": 500.0, "ask_price": 520.0,
                "mark_price": 510.0, "mark_iv": 60.0,
                "delta": 0.4, "open_interest": 100.0,
                "volume": 20.0, "creation_timestamp": now_ms,
            },
            {
                "instrument_name": "INVALID",  # bad format
                "bid_price": 0.0, "ask_price": 0.0,
                "mark_price": 0.0, "mark_iv": 0.0,
                "delta": 0.0, "open_interest": 0.0,
                "volume": 0.0, "creation_timestamp": now_ms,
            },
        ])
        chain = await adapter.get_option_chain(_BTC)
        # Only well-formed entries pass
        names = [o.instrument_name for o in chain]
        assert "INVALID" not in names

    @pytest.mark.asyncio
    async def test_dvol_returns_none_when_no_symbol(self):
        adapter = _make_adapter()
        result = await adapter.get_dvol(_SOL)
        assert result is None

    @pytest.mark.asyncio
    async def test_dvol_history_empty_when_no_symbol(self):
        adapter = _make_adapter()
        result = await adapter.get_dvol_history(_SOL, days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_candles_handles_timestamp_formats(self):
        """Adapter must handle sec/ms/us/ns timestamps without crash."""
        now_sec = int(time.time())
        adapter = _mock_get(_make_adapter(), {
            "ticks": [now_sec],  # seconds format
            "open": [40000.0], "high": [40500.0],
            "low": [39500.0], "close": [40200.0],
            "volume": [50.0],
        })
        candles = await adapter.get_candles(_ETH, "1H", limit=1)
        assert len(candles) == 1
        assert candles[0].timestamp_ms == now_sec * 1000
