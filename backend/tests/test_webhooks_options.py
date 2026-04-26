"""
Tests: webhook CRUD, option chain browser, webhook delivery mocking.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.schemas.market import Candle, OptionSummary
from main import create_app
import time


def _make_candles(n=100):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0+i*10, high=40050.0+i*10,
                   low=39950.0+i*10, close=40005.0+i*10, volume=100.0) for i in range(n)]


def _make_options():
    now_ms = int(time.time() * 1000)
    return [OptionSummary(
        instrument_name=f"BTC-12JAN25-{s}-C",
        underlying="BTC", strike=float(s), expiry_date="12JAN25", dte=12,
        option_type="call", bid=400.0, ask=420.0, mark_price=410.0, mid_price=410.0,
        mark_iv=55.0, delta=0.45, open_interest=200.0, volume_24h=30.0,
        last_updated_ms=now_ms,
    ) for s in [42000, 43000, 44000]]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=_make_options())
    a.get_dvol = AsyncMock(return_value=None)
    a.get_dvol_history = AsyncMock(return_value=[])
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


# ─── Webhook CRUD ─────────────────────────────────────────────────────────────

class TestWebhookCRUD:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/webhooks")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_add_discord_webhook(self, client):
        resp = client.post("/api/v1/webhooks", json={
            "name": "My Discord",
            "webhook_type": "discord",
            "url": "https://discord.com/api/webhooks/123/abc",
            "active": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Discord"
        assert data["webhook_type"] == "discord"
        assert data["active"] is True

    def test_add_telegram_webhook(self, client):
        resp = client.post("/api/v1/webhooks", json={
            "name": "My Telegram",
            "webhook_type": "telegram",
            "url": "https://api.telegram.org/botTOKEN/sendMessage",
            "extra": {"chat_id": "123456789"},
            "active": True,
        })
        assert resp.status_code == 200
        assert resp.json()["webhook_type"] == "telegram"

    def test_add_generic_webhook(self, client):
        resp = client.post("/api/v1/webhooks", json={
            "name": "Generic",
            "webhook_type": "generic",
            "url": "https://my-server.com/webhook",
            "active": True,
        })
        assert resp.status_code == 200

    def test_list_after_add(self, client):
        client.post("/api/v1/webhooks", json={
            "name": "test", "webhook_type": "discord",
            "url": "https://discord.com/123", "active": True,
        })
        assert client.get("/api/v1/webhooks").json()["count"] == 1

    def test_delete_webhook(self, client):
        add = client.post("/api/v1/webhooks", json={
            "name": "del_me", "webhook_type": "generic",
            "url": "https://example.com", "active": True,
        })
        wid = add.json()["id"]
        del_resp = client.delete(f"/api/v1/webhooks/{wid}")
        assert del_resp.status_code == 204
        assert client.get("/api/v1/webhooks").json()["count"] == 0

    def test_delete_unknown_404(self, client):
        resp = client.delete("/api/v1/webhooks/NOTEXIST")
        assert resp.status_code == 404

    def test_toggle_webhook(self, client):
        add = client.post("/api/v1/webhooks", json={
            "name": "toggle_me", "webhook_type": "discord",
            "url": "https://discord.com/123", "active": True,
        })
        wid = add.json()["id"]
        toggled = client.post(f"/api/v1/webhooks/{wid}/toggle")
        assert toggled.json()["active"] is False

    def test_test_webhook_fails_gracefully(self, client):
        """Test endpoint should return delivered=False on bad URL (not crash)."""
        add = client.post("/api/v1/webhooks", json={
            "name": "bad_url", "webhook_type": "generic",
            "url": "http://localhost:99999/nonexistent", "active": True,
        })
        wid = add.json()["id"]
        resp = client.post(f"/api/v1/webhooks/{wid}/test")
        assert resp.status_code == 200
        data = resp.json()
        # Should not crash — returns delivered=False with error
        assert "delivered" in data


# ─── Option Chain Browser ─────────────────────────────────────────────────────

class TestOptionChainBrowser:
    def test_chain_btc(self, client):
        resp = client.get("/api/v1/options/chain?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "spot_price" in data
        assert "total_contracts" in data
        assert "by_expiry" in data
        assert "timestamp_ms" in data

    def test_chain_field_structure(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC").json()
        assert "healthy_contracts" in data
        assert "expiry_count" in data
        assert "filter" in data

    def test_chain_filter_calls(self, client):
        resp = client.get("/api/v1/options/chain?underlying=BTC&type=call")
        assert resp.status_code == 200
        data = resp.json()
        for expiry, contracts in data["by_expiry"].items():
            for c in contracts:
                assert c["option_type"] == "call"

    def test_chain_dte_filter(self, client):
        resp = client.get("/api/v1/options/chain?underlying=BTC&min_dte=5&max_dte=20")
        assert resp.status_code == 200
        data = resp.json()
        for expiry, contracts in data["by_expiry"].items():
            for c in contracts:
                assert 5 <= c["dte"] <= 20

    def test_chain_unknown_404(self, client):
        resp = client.get("/api/v1/options/chain?underlying=FAKE")
        assert resp.status_code == 404

    def test_chain_no_options_400(self, client):
        resp = client.get("/api/v1/options/chain?underlying=XRP")
        assert resp.status_code == 400

    def test_chain_invalid_type_422(self, client):
        resp = client.get("/api/v1/options/chain?underlying=BTC&type=invalid")
        assert resp.status_code == 422

    def test_chain_contracts_health_assessed(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC").json()
        for expiry, contracts in data["by_expiry"].items():
            for c in contracts:
                assert "healthy" in c
                assert "health_score" in c
                assert "spread_pct" in c

    def test_chain_strikes_sorted_asc(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC").json()
        for expiry, contracts in data["by_expiry"].items():
            strikes = [c["strike"] for c in contracts]
            assert strikes == sorted(strikes)
