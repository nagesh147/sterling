"""
Tests: arrow store, positions filtering, config info, arrows endpoint.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from app.services import arrow_store
from main import create_app


def _make_candles(n=100, base=40000.0, trend=10.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * trend, high=base + i * trend + 50,
            low=base + i * trend - 50, close=base + i * trend + 5,
            volume=100.0,
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
    a.get_dvol_history = AsyncMock(return_value=[40.0, 55.0, 70.0])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c


# ─── Arrow Store ──────────────────────────────────────────────────────────────

class TestArrowStore:
    def test_record_and_retrieve(self):
        now = int(time.time() * 1000)
        arrow_store.record("BTC", "green", 42000.0, "long", "CONFIRMED_SETUP_ACTIVE", now, "test")
        arrows = arrow_store.get_arrows("BTC")
        assert len(arrows) == 1
        assert arrows[0].arrow_type == "green"
        assert arrows[0].underlying == "BTC"
        assert arrows[0].spot_price == 42000.0

    def test_newest_first(self):
        now = int(time.time() * 1000)
        arrow_store.record("ETH", "green", 3000.0, "long", "IDLE", now - 10000, "test")
        arrow_store.record("ETH", "red", 3100.0, "short", "IDLE", now, "test")
        arrows = arrow_store.get_arrows("ETH")
        assert arrows[0].arrow_type == "red"  # newest first

    def test_get_all_across_underlyings(self):
        now = int(time.time() * 1000)
        arrow_store.record("BTC", "green", 42000.0, "long", "IDLE", now, "test")
        arrow_store.record("ETH", "red", 3000.0, "short", "IDLE", now, "test")
        all_arrows = arrow_store.get_all()
        underlyings = {a.underlying for a in all_arrows}
        assert "BTC" in underlyings
        assert "ETH" in underlyings

    def test_empty_returns_empty_list(self):
        assert arrow_store.get_arrows("SOL") == []

    def test_clear_specific(self):
        now = int(time.time() * 1000)
        arrow_store.record("BTC", "green", 42000.0, "long", "IDLE", now, "test")
        arrow_store.record("ETH", "red", 3000.0, "short", "IDLE", now, "test")
        arrow_store.clear("BTC")
        assert arrow_store.get_arrows("BTC") == []
        assert len(arrow_store.get_arrows("ETH")) == 1

    def test_clear_all(self):
        now = int(time.time() * 1000)
        arrow_store.record("BTC", "green", 42000.0, "long", "IDLE", now, "test")
        arrow_store.clear()
        assert arrow_store.get_all() == []


# ─── Arrows Endpoint ──────────────────────────────────────────────────────────

class TestArrowsEndpoint:
    def test_get_arrows_btc_empty(self, client):
        resp = client.get("/api/v1/directional/arrows/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["count"] == 0
        assert data["arrows"] == []

    def test_get_arrows_after_record(self, client):
        now = int(time.time() * 1000)
        arrow_store.record("BTC", "green", 42000.0, "long", "CONFIRMED_SETUP_ACTIVE", now, "test")
        resp = client.get("/api/v1/directional/arrows/BTC")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1
        assert resp.json()["arrows"][0]["arrow_type"] == "green"

    def test_get_arrows_unknown_404(self, client):
        resp = client.get("/api/v1/directional/arrows/FAKE")
        assert resp.status_code == 404

    def test_get_all_arrows(self, client):
        resp = client.get("/api/v1/directional/arrows")
        assert resp.status_code == 200
        assert "arrows" in resp.json()
        assert resp.json()["underlying"] == "ALL"


# ─── Positions Filtering ──────────────────────────────────────────────────────

class TestPositionsFilter:
    def test_filter_by_underlying(self, client):
        # Empty anyway, but endpoint should accept the param
        resp = client.get("/api/v1/positions?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["underlying"] == "BTC" for p in data["positions"])

    def test_filter_by_status(self, client):
        resp = client.get("/api/v1/positions?status=open")
        assert resp.status_code == 200
        assert all(p["status"] == "open" for p in resp.json()["positions"])

    def test_filter_by_status_closed(self, client):
        resp = client.get("/api/v1/positions?status=closed")
        assert resp.status_code == 200
        assert all(p["status"] == "closed" for p in resp.json()["positions"])

    def test_no_filter_returns_all(self, client):
        resp = client.get("/api/v1/positions")
        assert resp.status_code == 200
        assert "positions" in resp.json()


# ─── Config Info ──────────────────────────────────────────────────────────────

class TestConfigInfo:
    def test_info_returns_all_fields(self, client):
        resp = client.get("/api/v1/config/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "exchange_adapter" in data
        assert "supported_underlyings" in data
        assert "underlyings_with_options" in data
        assert "adapter_stack" in data
        assert "db_path" in data

    def test_info_instruments(self, client):
        data = client.get("/api/v1/config/info").json()
        assert "BTC" in data["supported_underlyings"]
        assert "ETH" in data["underlyings_with_options"]
        assert "XRP" not in data["underlyings_with_options"]

    def test_info_adapter_stack_format(self, client):
        stack = client.get("/api/v1/config/info").json()["adapter_stack"]
        assert "CachingAdapter" in stack
        assert "RetryingAdapter" in stack
