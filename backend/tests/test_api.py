"""
API integration tests — mock the adapter on app.state.
No live network calls.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from main import create_app
from app.schemas.market import Candle, OptionSummary


def _make_candles(n: int = 100, base: float = 40000.0) -> list[Candle]:
    import numpy as np
    np.random.seed(0)
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * 10,
            high=base + i * 10 + 50,
            low=base + i * 10 - 50,
            close=base + i * 10 + 5,
            volume=100.0,
        )
        for i in range(n)
    ]


def _make_adapter_mock():
    adapter = MagicMock()
    adapter.ping = AsyncMock(return_value=True)
    adapter.get_index_price = AsyncMock(return_value=42000.0)
    adapter.get_spot_price = AsyncMock(return_value=42000.0)
    adapter.get_perp_price = AsyncMock(return_value=42050.0)
    adapter.get_candles = AsyncMock(return_value=_make_candles())
    adapter.get_option_chain = AsyncMock(return_value=[])
    adapter.get_dvol = AsyncMock(return_value=55.0)
    adapter.get_dvol_history = AsyncMock(return_value=[40.0, 45.0, 55.0, 70.0])
    adapter.close = AsyncMock(return_value=None)
    return adapter


@pytest.fixture()
def client():
    app = create_app()
    adapter = _make_adapter_mock()
    app.state.adapter = adapter

    with TestClient(app, raise_server_exceptions=True) as c:
        c.app.state.adapter = adapter
        yield c


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "paper_trading" in data

    def test_health_returns_timestamp(self, client):
        resp = client.get("/health")
        assert resp.json()["timestamp_ms"] > 0


class TestInstruments:
    def test_list_instruments(self, client):
        resp = client.get("/api/v1/instruments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        underlyings = {i["underlying"] for i in data["instruments"]}
        assert "BTC" in underlyings
        assert "ETH" in underlyings

    def test_get_btc(self, client):
        resp = client.get("/api/v1/instruments/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["instrument"]["underlying"] == "BTC"
        assert data["options_available"] is True

    def test_get_xrp_no_options(self, client):
        resp = client.get("/api/v1/instruments/XRP")
        assert resp.status_code == 200
        assert resp.json()["options_available"] is False

    def test_unknown_returns_404(self, client):
        resp = client.get("/api/v1/instruments/DOGE")
        assert resp.status_code == 404

    def test_case_insensitive(self, client):
        resp = client.get("/api/v1/instruments/eth")
        assert resp.status_code == 200
        assert resp.json()["instrument"]["underlying"] == "ETH"


class TestDirectionalStatus:
    def test_status_btc(self, client):
        resp = client.get("/api/v1/directional/status?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "paper_mode" in data
        assert "real_public_data" in data
        assert "exchange_status" in data

    def test_status_unknown(self, client):
        resp = client.get("/api/v1/directional/status?underlying=FAKE")
        assert resp.status_code == 200
        assert resp.json()["loaded"] is False


class TestMarketSnapshot:
    def test_snapshot_btc(self, client):
        resp = client.get("/api/v1/directional/debug/market-snapshot?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["spot_price"] == 42000.0
        assert data["candles_4h_count"] > 0

    def test_snapshot_unknown_404(self, client):
        resp = client.get("/api/v1/directional/debug/market-snapshot?underlying=FAKE")
        assert resp.status_code == 404


class TestPreview:
    def test_preview_btc(self, client):
        resp = client.get("/api/v1/directional/preview?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "state" in data
        assert "direction" in data

    def test_preview_xrp_filtered(self, client):
        resp = client.get("/api/v1/directional/preview?underlying=XRP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "FILTERED"

    def test_preview_unknown_404(self, client):
        resp = client.get("/api/v1/directional/preview?underlying=FAKE")
        assert resp.status_code == 404


class TestRunOnce:
    def test_run_once_btc(self, client):
        resp = client.post("/api/v1/directional/run-once?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["paper_mode"] is True
        assert "state" in data
        assert "recommendation" in data

    def test_run_once_eth(self, client):
        resp = client.post("/api/v1/directional/run-once?underlying=ETH")
        assert resp.status_code == 200
        assert resp.json()["underlying"] == "ETH"

    def test_run_once_xrp_no_options(self, client):
        resp = client.post("/api/v1/directional/run-once?underlying=XRP")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "FILTERED"
        assert data["recommendation"] == "no_trade"

    def test_run_once_unknown_404(self, client):
        resp = client.post("/api/v1/directional/run-once?underlying=UNKNOWN")
        assert resp.status_code == 404
