"""Kite router: multi-tenant CRUD, routing guard, safety gate, paper happy paths."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.services import live_safety
from app.services.exchanges.kite.client import KiteClient
from main import create_app


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    app = create_app()
    app.state.adapter = _mock_adapter()
    with TestClient(app) as c:
        c.app.state.adapter = app.state.adapter
        yield c


@pytest.fixture(autouse=True)
def _reset_safety():
    live_safety.set_kill_switch(False)
    yield
    live_safety.set_kill_switch(False)


def _add_account(client, headers=None, label="A", paper=True):
    r = client.post("/api/v1/kite/accounts", headers=headers or {}, json={
        "label": label, "api_key": "apikey123", "api_secret": "topsecret", "is_paper": paper,
    })
    assert r.status_code == 200, r.text
    return r.json()


# ─── Account CRUD + multi-tenancy ────────────────────────────────────────────
def test_add_account_redacts_secret_and_auto_activates(client):
    acc = _add_account(client)
    assert acc["is_active"] is True
    assert acc["api_key_hint"] == "****y123"
    assert "topsecret" not in str(acc)


def test_user_isolation_via_header(client):
    _add_account(client, headers={"X-User-Id": "alice"})
    bob = client.get("/api/v1/kite/accounts", headers={"X-User-Id": "bob"}).json()
    assert bob["count"] == 0
    alice = client.get("/api/v1/kite/accounts", headers={"X-User-Id": "alice"}).json()
    assert alice["count"] == 1


def test_update_and_delete_account(client):
    acc = _add_account(client)
    up = client.put(f"/api/v1/kite/accounts/{acc['id']}", json={"label": "renamed"})
    assert up.json()["label"] == "renamed"
    d = client.delete(f"/api/v1/kite/accounts/{acc['id']}")
    assert d.status_code == 204
    assert client.get("/api/v1/kite/accounts").json()["count"] == 0


# ─── Routing guard ───────────────────────────────────────────────────────────
def test_holdings_requires_active_account(client):
    r = client.get("/api/v1/kite/holdings")
    assert r.status_code == 409


def test_login_url_after_account_added(client):
    _add_account(client)
    r = client.get("/api/v1/kite/login-url")
    assert r.status_code == 200
    assert "api_key=apikey123" in r.json()["login_url"]


def test_status_reports_not_logged_in(client):
    _add_account(client)
    s = client.get("/api/v1/kite/status").json()
    assert s["connected"] is False
    assert "login" in s["message"].lower()


# ─── Orders / safety ─────────────────────────────────────────────────────────
def test_place_order_paper_happy_path(client):
    _add_account(client, paper=True)
    r = client.post("/api/v1/kite/orders", json={
        "tradingsymbol": "INFY", "exchange": "NSE", "transaction_type": "BUY",
        "quantity": 1, "order_type": "MARKET", "product": "CNC",
    })
    assert r.status_code == 200, r.text
    assert r.json()["order_id"].startswith("PAPER-")


def test_place_order_blocked_by_kill_switch(client):
    _add_account(client, paper=True)
    live_safety.set_kill_switch(True, reason="test halt")
    r = client.post("/api/v1/kite/orders", json={
        "tradingsymbol": "INFY", "exchange": "NSE", "transaction_type": "BUY",
        "quantity": 1, "order_type": "MARKET", "product": "CNC",
    })
    assert r.status_code == 423
    assert r.json()["detail"]["code"] == "kill_switch"


def test_paper_holdings_and_positions_empty(client):
    _add_account(client, paper=True)
    assert client.get("/api/v1/kite/holdings").json() == []
    assert client.get("/api/v1/kite/positions").json() == {"positions": []}


def test_instruments_search(client, monkeypatch):
    _add_account(client, paper=True)
    csv = ("instrument_token,tradingsymbol,name,segment,exchange\n"
           "408065,INFY,INFOSYS,NSE,NSE\n")

    async def fake_fetch(self, exchange):
        return csv
    monkeypatch.setattr(KiteClient, "_fetch_instruments_csv", fake_fetch)
    r = client.get("/api/v1/kite/instruments", params={"exchange": "NSE", "query": "INFY"})
    assert r.status_code == 200
    assert r.json()["instruments"][0]["tradingsymbol"] == "INFY"


def test_ticker_subscribe_without_live_session(client):
    _add_account(client, paper=True)
    r = client.post("/api/v1/kite/ticker/subscribe", json={"instrument_tokens": [408065], "mode": "ltp"})
    assert r.status_code == 200
    assert r.json()["ok"] is False  # paper account → no live ticker
