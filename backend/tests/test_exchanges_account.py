"""
Tests: exchange config CRUD, account endpoints, Delta India adapter (mocked).
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from app.services.exchanges.adapters.delta_india import (
    DeltaIndiaAdapter, _ts_ms, _delta_dte,
)
from app.services.exchanges.instrument_registry import get_instrument
from main import create_app


def _make_candles(n=100, base=40000.0, trend=10.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * trend, high=base + i * trend + 50,
            low=base + i * trend - 50, close=base + i * trend + 5, volume=100.0,
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
    a.get_dvol = AsyncMock(return_value=None)
    a.get_dvol_history = AsyncMock(return_value=[])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    from app.services import exchange_account_store as eas
    eas._loaded = False
    eas._configs.clear()
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c
    eas._configs.clear()
    eas._loaded = False


# ─── Delta India helpers ──────────────────────────────────────────────────────

class TestDeltaHelpers:
    def test_ts_ms_seconds(self):
        assert _ts_ms(1_700_000_000) == 1_700_000_000_000

    def test_ts_ms_milliseconds(self):
        assert _ts_ms(1_700_000_000_000) == 1_700_000_000_000

    def test_dte_future(self):
        dte = _delta_dte("31DEC35")  # 2035
        assert dte > 0

    def test_dte_invalid(self):
        assert _delta_dte("BADDATE") == -1


# ─── Delta India adapter (mocked HTTP) ───────────────────────────────────────

class TestDeltaAdapterPublic:
    @pytest.mark.asyncio
    async def test_ping_success(self):
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={"success": True, "result": []})
        assert await adapter.ping()

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(side_effect=Exception("down"))
        assert not await adapter.ping()

    @pytest.mark.asyncio
    async def test_get_index_price(self):
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": {"mark_price": "43000.5", "spot_price": "43000.5", "last_price": "43000"},
        })
        price = await adapter.get_index_price(get_instrument("BTC"))
        assert price == pytest.approx(43000.5)

    @pytest.mark.asyncio
    async def test_get_candles(self):
        now = int(time.time())
        adapter = DeltaIndiaAdapter()
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": [
                {"time": now - 3600, "open": 42000, "high": 42500, "low": 41800, "close": 42300, "volume": 100},
                {"time": now, "open": 42300, "high": 42700, "low": 42100, "close": 42600, "volume": 120},
            ],
        })
        candles = await adapter.get_candles(get_instrument("BTC"), "1H", limit=2)
        assert len(candles) == 2
        assert candles[0].close == pytest.approx(42300.0)

    @pytest.mark.asyncio
    async def test_dvol_returns_none(self):
        adapter = DeltaIndiaAdapter()
        assert await adapter.get_dvol(get_instrument("BTC")) is None

    @pytest.mark.asyncio
    async def test_dvol_history_empty(self):
        adapter = DeltaIndiaAdapter()
        assert await adapter.get_dvol_history(get_instrument("BTC")) == []

    @pytest.mark.asyncio
    async def test_option_chain_parses(self):
        adapter = DeltaIndiaAdapter()
        now = int(time.time())
        adapter._public_get = AsyncMock(return_value={
            "success": True,
            "result": [
                {
                    "symbol": "C-BTC-43000-31DEC35",
                    "bid": 500.0, "ask": 520.0, "mark_price": 510.0,
                    "mark_iv": 60.0, "delta": 0.45, "oi": 100.0,
                    "volume": 10.0, "created_at": now,
                },
                {"symbol": "BAD", "bid": 0, "ask": 0},  # malformed — should be skipped
            ],
        })
        chain = await adapter.get_option_chain(get_instrument("BTC"))
        assert len(chain) == 1
        assert chain[0].option_type == "call"
        assert chain[0].strike == 43000.0


class TestDeltaAdapterAccount:
    @pytest.mark.asyncio
    async def test_paper_mode_balances(self):
        adapter = DeltaIndiaAdapter(is_paper=True)
        balances = await adapter.get_balances()
        assert len(balances) > 0
        assets = {b.asset for b in balances}
        assert "BTC" in assets
        assert "USDT" in assets

    @pytest.mark.asyncio
    async def test_paper_mode_positions_empty(self):
        adapter = DeltaIndiaAdapter(is_paper=True)
        assert await adapter.get_positions() == []

    @pytest.mark.asyncio
    async def test_paper_mode_orders_empty(self):
        adapter = DeltaIndiaAdapter(is_paper=True)
        assert await adapter.get_open_orders() == []

    @pytest.mark.asyncio
    async def test_paper_mode_fills_empty(self):
        adapter = DeltaIndiaAdapter(is_paper=True)
        assert await adapter.get_fills() == []

    @pytest.mark.asyncio
    async def test_paper_mode_test_connection(self):
        adapter = DeltaIndiaAdapter(is_paper=True)
        assert await adapter.test_connection()

    @pytest.mark.asyncio
    async def test_real_mode_requires_credentials(self):
        adapter = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=False)
        with pytest.raises(RuntimeError, match="credentials"):
            await adapter.get_balances()

    @pytest.mark.asyncio
    async def test_portfolio_snapshot_paper(self):
        adapter = DeltaIndiaAdapter(is_paper=True)
        snap = await adapter.get_portfolio_snapshot()
        assert snap.exchange == "delta_india"
        assert snap.positions_count == 0
        assert snap.total_balance_usd > 0


# ─── Exchange Config API ──────────────────────────────────────────────────────

class TestExchangesAPI:
    def test_list_exchanges(self, client):
        resp = client.get("/api/v1/exchanges")
        assert resp.status_code == 200
        data = resp.json()
        assert "exchanges" in data
        assert data["count"] > 0

    def test_default_delta_india_present(self, client):
        resp = client.get("/api/v1/exchanges")
        names = [e["name"] for e in resp.json()["exchanges"]]
        assert "delta_india" in names

    def test_delta_india_is_active(self, client):
        resp = client.get("/api/v1/exchanges")
        active = [e for e in resp.json()["exchanges"] if e["is_active"]]
        assert len(active) >= 1
        assert active[0]["name"] == "delta_india"

    def test_add_exchange(self, client):
        resp = client.post("/api/v1/exchanges", json={
            "name": "okx",
            "display_name": "OKX",
            "api_key": "test_key",
            "api_secret": "test_secret",
            "is_paper": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "okx"
        assert data["api_key_hint"].startswith("****")

    def test_add_unsupported_exchange_400(self, client):
        resp = client.post("/api/v1/exchanges", json={
            "name": "bybit",
            "display_name": "Bybit",
            "api_key": "",
            "api_secret": "",
            "is_paper": True,
        })
        assert resp.status_code == 400

    def test_get_exchange(self, client):
        resp = client.get("/api/v1/exchanges")
        eid = resp.json()["exchanges"][0]["id"]
        resp2 = client.get(f"/api/v1/exchanges/{eid}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == eid

    def test_get_unknown_404(self, client):
        resp = client.get("/api/v1/exchanges/NONEXISTENT")
        assert resp.status_code == 404

    def test_update_exchange(self, client):
        resp = client.get("/api/v1/exchanges")
        eid = resp.json()["exchanges"][0]["id"]
        resp2 = client.put(f"/api/v1/exchanges/{eid}", json={
            "api_key": "NEW_KEY_123456",
            "is_paper": True,
        })
        assert resp2.status_code == 200
        # API key hint updated
        assert "KEY" in resp2.json()["api_key_hint"].upper() or resp2.json()["api_key_hint"].endswith("3456")

    def test_activate_exchange(self, client):
        # Add second exchange
        resp = client.post("/api/v1/exchanges", json={
            "name": "okx", "display_name": "OKX",
            "api_key": "", "api_secret": "", "is_paper": True,
        })
        new_id = resp.json()["id"]
        # Activate it
        resp2 = client.post(f"/api/v1/exchanges/{new_id}/activate")
        assert resp2.status_code == 200
        assert resp2.json()["is_active"] is True
        # Previous one should no longer be active
        resp3 = client.get("/api/v1/exchanges")
        active_ids = [e["id"] for e in resp3.json()["exchanges"] if e["is_active"]]
        assert active_ids == [new_id]

    def test_delete_exchange(self, client):
        resp = client.post("/api/v1/exchanges", json={
            "name": "okx", "display_name": "OKX",
            "api_key": "", "api_secret": "", "is_paper": True,
        })
        eid = resp.json()["id"]
        del_resp = client.delete(f"/api/v1/exchanges/{eid}")
        assert del_resp.status_code == 204

    def test_test_connection_paper(self, client):
        resp = client.get("/api/v1/exchanges")
        eid = resp.json()["exchanges"][0]["id"]
        resp2 = client.post(f"/api/v1/exchanges/{eid}/test")
        assert resp2.status_code == 200
        data = resp2.json()
        assert "connected" in data

    def test_supported_exchanges(self, client):
        resp = client.get("/api/v1/exchanges/supported")
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()["exchanges"]]
        assert "delta_india" in names
        assert "deribit" in names
        assert "okx" in names


# ─── Account API ──────────────────────────────────────────────────────────────

class TestAccountAPI:
    def test_account_info(self, client):
        resp = client.get("/api/v1/account/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["exchange_name"] == "delta_india"

    def test_account_summary(self, client):
        resp = client.get("/api/v1/account/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_paper" in data
        assert "is_connected" in data
        assert data["is_paper"] is True

    def test_account_balances_paper(self, client):
        resp = client.get("/api/v1/account/balances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_paper"] is True
        assert data["count"] > 0
        assets = [b["asset"] for b in data["balances"]]
        assert "BTC" in assets
        assert "USDT" in assets

    def test_account_positions_paper(self, client):
        resp = client.get("/api/v1/account/positions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_paper"] is True
        assert data["positions"] == []

    def test_account_orders_paper(self, client):
        resp = client.get("/api/v1/account/orders")
        assert resp.status_code == 200
        assert resp.json()["orders"] == []

    def test_account_fills_paper(self, client):
        resp = client.get("/api/v1/account/fills")
        assert resp.status_code == 200
        assert resp.json()["fills"] == []

    def test_account_positions_filter(self, client):
        resp = client.get("/api/v1/account/positions?underlying=BTC")
        assert resp.status_code == 200
        assert "positions" in resp.json()
