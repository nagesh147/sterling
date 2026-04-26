"""
Tests for: watchlist, history, config, CachingAdapter.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from main import create_app
from app.services.cache import CachingAdapter
from app.services.exchanges.instrument_registry import get_instrument


def _make_candles(n=100, base=40000.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * 10, high=base + i * 10 + 50,
            low=base + i * 10 - 50, close=base + i * 10 + 5, volume=100.0,
        )
        for i in range(n)
    ]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=55.0)
    a.get_dvol_history = AsyncMock(return_value=[40.0, 50.0, 60.0])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    from app.services import eval_history
    eval_history.clear()
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app, raise_server_exceptions=True) as c:
        c.app.state.adapter = adapter
        yield c


# ─── Watchlist ────────────────────────────────────────────────────────────────

class TestWatchlist:
    def test_returns_all_instruments(self, client):
        resp = client.get("/api/v1/directional/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        underlyings = {item["underlying"] for item in data["items"]}
        assert "BTC" in underlyings
        assert "ETH" in underlyings
        assert "XRP" in underlyings

    def test_each_item_has_state(self, client):
        resp = client.get("/api/v1/directional/watchlist")
        for item in resp.json()["items"]:
            assert "state" in item
            assert "direction" in item
            assert "underlying" in item

    def test_has_timestamp(self, client):
        resp = client.get("/api/v1/directional/watchlist")
        assert resp.json()["timestamp_ms"] > 0


# ─── Eval History ─────────────────────────────────────────────────────────────

class TestEvalHistory:
    def test_empty_history(self, client):
        resp = client.get("/api/v1/directional/history/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["history"] == []
        assert data["count"] == 0

    def test_history_grows_after_run_once(self, client):
        client.post("/api/v1/directional/run-once?underlying=BTC")
        resp = client.get("/api/v1/directional/history/BTC")
        assert resp.json()["count"] == 1

    def test_history_accumulates(self, client):
        client.post("/api/v1/directional/run-once?underlying=BTC")
        client.post("/api/v1/directional/run-once?underlying=BTC")
        assert client.get("/api/v1/directional/history/BTC").json()["count"] == 2

    def test_history_item_fields(self, client):
        client.post("/api/v1/directional/run-once?underlying=ETH")
        item = client.get("/api/v1/directional/history/ETH").json()["history"][0]
        assert "state" in item
        assert "recommendation" in item
        assert "no_trade_score" in item
        assert "timestamp_ms" in item

    def test_unknown_underlying_404(self, client):
        resp = client.get("/api/v1/directional/history/FAKE")
        assert resp.status_code == 404

    def test_history_isolated_by_underlying(self, client):
        client.post("/api/v1/directional/run-once?underlying=BTC")
        eth_hist = client.get("/api/v1/directional/history/ETH").json()
        assert eth_hist["count"] == 0


# ─── Config ───────────────────────────────────────────────────────────────────

class TestRiskConfig:
    def test_get_default_config(self, client):
        resp = client.get("/api/v1/config/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert "capital" in data
        assert "max_position_pct" in data
        assert "max_contracts" in data

    def test_update_config(self, client):
        resp = client.put("/api/v1/config/risk", json={
            "capital": 50000.0,
            "max_position_pct": 0.03,
            "max_contracts": 5,
            "partial_profit_r1": 1.5,
            "partial_profit_r2": 2.0,
            "time_stop_dte": 3,
            "financial_stop_pct": 0.5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["capital"] == 50000.0
        assert data["max_contracts"] == 5

    def test_reset_config(self, client):
        # Change first
        client.put("/api/v1/config/risk", json={
            "capital": 1.0, "max_position_pct": 0.01,
            "max_contracts": 1, "partial_profit_r1": 1.5,
            "partial_profit_r2": 2.0, "time_stop_dte": 3,
            "financial_stop_pct": 0.5,
        })
        # Then reset
        resp = client.post("/api/v1/config/risk/reset")
        assert resp.status_code == 200
        # Should be back to app defaults (100k)
        assert resp.json()["capital"] == 100_000.0

    def test_run_once_uses_updated_config(self, client):
        # With very low capital, should size to 1 contract
        client.put("/api/v1/config/risk", json={
            "capital": 100.0, "max_position_pct": 0.05,
            "max_contracts": 10, "partial_profit_r1": 1.5,
            "partial_profit_r2": 2.0, "time_stop_dte": 3,
            "financial_stop_pct": 0.5,
        })
        # run-once should succeed regardless (no options chain → no_trade)
        resp = client.post("/api/v1/directional/run-once?underlying=BTC")
        assert resp.status_code == 200


# ─── CachingAdapter unit tests ────────────────────────────────────────────────

class TestCachingAdapter:
    def _inner(self):
        inner = MagicMock()
        inner.get_index_price = AsyncMock(return_value=42000.0)
        inner.get_candles = AsyncMock(return_value=_make_candles())
        inner.get_dvol = AsyncMock(return_value=55.0)
        inner.get_dvol_history = AsyncMock(return_value=[40.0, 55.0])
        inner.close = AsyncMock(return_value=None)
        return inner

    @pytest.mark.asyncio
    async def test_price_cached(self):
        inner = self._inner()
        adapter = CachingAdapter(inner)
        inst = get_instrument("BTC")
        v1 = await adapter.get_index_price(inst)
        v2 = await adapter.get_index_price(inst)
        assert v1 == v2
        inner.get_index_price.assert_called_once()  # second call was cached

    @pytest.mark.asyncio
    async def test_candles_cached(self):
        inner = self._inner()
        adapter = CachingAdapter(inner)
        inst = get_instrument("BTC")
        await adapter.get_candles(inst, "1H", limit=100)
        await adapter.get_candles(inst, "1H", limit=100)
        inner.get_candles.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_resolutions_cached_separately(self):
        inner = self._inner()
        adapter = CachingAdapter(inner)
        inst = get_instrument("BTC")
        await adapter.get_candles(inst, "1H", limit=100)
        await adapter.get_candles(inst, "4H", limit=100)
        assert inner.get_candles.call_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_clears_cache(self):
        inner = self._inner()
        adapter = CachingAdapter(inner)
        inst = get_instrument("BTC")
        await adapter.get_index_price(inst)
        adapter.invalidate("price:")
        await adapter.get_index_price(inst)
        assert inner.get_index_price.call_count == 2

    @pytest.mark.asyncio
    async def test_close_delegates(self):
        inner = self._inner()
        adapter = CachingAdapter(inner)
        await adapter.close()
        inner.close.assert_called_once()
