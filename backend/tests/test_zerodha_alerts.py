"""
Tests: Zerodha adapter, alert system.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from app.services.exchanges.adapters.zerodha import ZerodhaAdapter, _parse_kite_ts
from app.services.exchanges.instrument_registry import get_instrument
from app.services import alert_store
from app.schemas.alerts import AlertCondition, AlertCreate, AlertStatus
from main import create_app


def _make_candles(n=100):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0 + i*10, high=40050.0+i*10,
                   low=39950.0+i*10, close=40005.0+i*10, volume=100.0) for i in range(n)]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
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


# ─── Zerodha Adapter ─────────────────────────────────────────────────────────

class TestZerodhaHelpers:
    def test_parse_kite_ts_valid(self):
        ts = _parse_kite_ts("2024-01-15 10:30:00")
        assert ts > 0
        assert ts > 1_700_000_000_000

    def test_parse_kite_ts_invalid(self):
        ts = _parse_kite_ts("bad")
        assert ts > 0  # returns current time


class TestZerodhaAdapterPaper:
    @pytest.mark.asyncio
    async def test_ping_paper(self):
        adapter = ZerodhaAdapter(is_paper=True)
        assert await adapter.ping()

    @pytest.mark.asyncio
    async def test_test_connection_paper(self):
        adapter = ZerodhaAdapter(is_paper=True)
        assert await adapter.test_connection()

    @pytest.mark.asyncio
    async def test_balances_paper(self):
        adapter = ZerodhaAdapter(is_paper=True)
        bals = await adapter.get_balances()
        assert len(bals) > 0
        assets = {b.asset for b in bals}
        assert any("INR" in a for a in assets)

    @pytest.mark.asyncio
    async def test_positions_paper_empty(self):
        adapter = ZerodhaAdapter(is_paper=True)
        assert await adapter.get_positions() == []

    @pytest.mark.asyncio
    async def test_orders_paper_empty(self):
        adapter = ZerodhaAdapter(is_paper=True)
        assert await adapter.get_open_orders() == []

    @pytest.mark.asyncio
    async def test_fills_paper_empty(self):
        adapter = ZerodhaAdapter(is_paper=True)
        assert await adapter.get_fills() == []

    @pytest.mark.asyncio
    async def test_candles_stub(self):
        adapter = ZerodhaAdapter(is_paper=True)
        # Candles not yet implemented → returns []
        candles = await adapter.get_candles(get_instrument("BTC"), "1H", 10)
        assert candles == []

    @pytest.mark.asyncio
    async def test_live_mode_requires_credentials(self):
        adapter = ZerodhaAdapter(is_paper=False, api_key="", access_token="")
        with pytest.raises(RuntimeError, match="access_token"):
            await adapter.get_balances()

    @pytest.mark.asyncio
    async def test_portfolio_snapshot_paper(self):
        adapter = ZerodhaAdapter(is_paper=True)
        snap = await adapter.get_portfolio_snapshot()
        assert snap.exchange == "zerodha"
        assert snap.positions_count == 0


class TestZerodhaExchangeAPI:
    def test_zerodha_in_supported(self, client):
        resp = client.get("/api/v1/exchanges/supported")
        names = [e["name"] for e in resp.json()["exchanges"]]
        assert "zerodha" in names

    def test_add_zerodha(self, client):
        resp = client.post("/api/v1/exchanges", json={
            "name": "zerodha",
            "display_name": "My Zerodha Account",
            "api_key": "kite_api_key_here",
            "api_secret": "kite_api_secret",
            "is_paper": True,
            "extra": {"access_token": "session_token_here"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "zerodha"
        assert data["is_paper"] is True

    def test_zerodha_account_summary(self, client):
        # Add Zerodha and activate
        add_resp = client.post("/api/v1/exchanges", json={
            "name": "zerodha", "display_name": "Zerodha",
            "api_key": "k", "api_secret": "s", "is_paper": True, "extra": {},
        })
        eid = add_resp.json()["id"]
        client.post(f"/api/v1/exchanges/{eid}/activate")

        resp = client.get("/api/v1/account/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_paper"] is True
        assert "zerodha" in data["exchange_name"]


# ─── Alert System ─────────────────────────────────────────────────────────────

class TestAlertStore:
    def test_add_and_list(self):
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.PRICE_ABOVE, threshold=50000.0
        ))
        assert alert.id
        assert alert.status == AlertStatus.ACTIVE
        alerts = alert_store.list_alerts("BTC")
        assert len(alerts) == 1

    def test_fire_alert(self):
        alert = alert_store.add_alert(AlertCreate(
            underlying="ETH", condition=AlertCondition.IVR_ABOVE, threshold=70.0
        ))
        fired = alert_store.fire_alert(alert.id, trigger_value=75.0)
        assert fired is not None
        assert fired.status == AlertStatus.TRIGGERED
        assert fired.trigger_value == 75.0

    def test_dismiss(self):
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.SIGNAL_GREEN_ARROW
        ))
        dismissed = alert_store.dismiss_alert(alert.id)
        assert dismissed.status == AlertStatus.DISMISSED

    def test_check_price_above_triggered(self):
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.PRICE_ABOVE, threshold=40000.0
        ))
        result = alert_store.check_alert(alert, spot_price=45000.0)
        assert result.triggered
        assert result.current_value == 45000.0

    def test_check_price_above_not_triggered(self):
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.PRICE_ABOVE, threshold=50000.0
        ))
        result = alert_store.check_alert(alert, spot_price=42000.0)
        assert not result.triggered

    def test_check_green_arrow(self):
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.SIGNAL_GREEN_ARROW
        ))
        result = alert_store.check_alert(alert, green_arrow=True)
        assert result.triggered

    def test_counts(self):
        alert_store.add_alert(AlertCreate(underlying="BTC", condition=AlertCondition.SIGNAL_RED_ARROW))
        assert alert_store.active_count() == 1
        assert alert_store.triggered_count() == 0


class TestAlertAPI:
    def test_list_empty(self, client):
        resp = client.get("/api/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts"] == []
        assert data["active_count"] == 0

    def test_create_alert(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC",
            "condition": "price_above",
            "threshold": 50000.0,
            "notes": "BTC ATH watch",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["status"] == "active"

    def test_create_alert_unknown_underlying(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "FAKE", "condition": "price_above", "threshold": 100.0
        })
        assert resp.status_code == 404

    def test_list_after_create(self, client):
        client.post("/api/v1/alerts", json={
            "underlying": "ETH", "condition": "ivr_above", "threshold": 70.0
        })
        resp = client.get("/api/v1/alerts")
        assert resp.json()["active_count"] == 1

    def test_filter_by_underlying(self, client):
        client.post("/api/v1/alerts", json={"underlying": "BTC", "condition": "price_above", "threshold": 50000.0})
        client.post("/api/v1/alerts", json={"underlying": "ETH", "condition": "price_above", "threshold": 3000.0})
        resp = client.get("/api/v1/alerts?underlying=BTC")
        alerts = resp.json()["alerts"]
        assert all(a["underlying"] == "BTC" for a in alerts)

    def test_check_alerts(self, client):
        client.post("/api/v1/alerts", json={"underlying": "BTC", "condition": "price_above", "threshold": 50000.0})
        resp = client.post("/api/v1/alerts/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "checked" in data
        assert "newly_triggered" in data

    def test_dismiss_alert(self, client):
        create = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "signal_green_arrow"
        })
        aid = create.json()["id"]
        resp = client.post(f"/api/v1/alerts/{aid}/dismiss")
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"

    def test_delete_alert(self, client):
        create = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_below", "threshold": 30000.0
        })
        aid = create.json()["id"]
        del_resp = client.delete(f"/api/v1/alerts/{aid}")
        assert del_resp.status_code == 204

    def test_list_triggered(self, client):
        resp = client.get("/api/v1/alerts/triggered")
        assert resp.status_code == 200
        assert isinstance(resp.json()["alerts"], list)

    def test_delete_unknown_404(self, client):
        resp = client.delete("/api/v1/alerts/DEADBEEF")
        assert resp.status_code == 404
