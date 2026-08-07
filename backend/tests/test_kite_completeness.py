"""
Completeness suite — the Kite Connect v3 surfaces added to reach 100% parity:
session refresh, holdings auctions + authorisation, MF order/SIP lifecycle + MF
instruments, and the native Alerts API. Client-level payload mapping via
httpx.MockTransport (no app import, fast).
"""
import json
from urllib.parse import parse_qs

import httpx
import pytest

from app.services.exchanges.kite import constants as K
from app.services.exchanges.kite.client import KiteClient
from app.services.exchanges.kite.errors import KiteTokenError


def _client(handler, *, is_paper=False):
    c = KiteClient(api_key="ak", api_secret="sec", access_token="tok", is_paper=is_paper)
    c._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.kite.trade",
        headers={"X-Kite-Version": "3"},
    )
    return c


def _capture(payload=None, *, text=None):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query"] = dict(request.url.params)
        # keep repeated query keys too (e.g. ?uuid=a&uuid=b)
        seen["query_multi"] = parse_qs(request.url.query.decode())
        body = request.content.decode() if request.content else ""
        seen["raw"] = body
        seen["form"] = {k: v[0] for k, v in parse_qs(body).items()} if body else {}
        seen["ctype"] = request.headers.get("content-type", "")
        if text is not None:
            return httpx.Response(200, text=text)
        return httpx.Response(200, json={"status": "success", "data": payload if payload is not None else {}})

    return handler, seen


# ─── Session refresh ─────────────────────────────────────────────────────────
async def test_renew_access_token_posts_checksum():
    handler, seen = _capture({"access_token": "NEWTOK"})
    c = _client(handler)
    out = await c.renew_access_token("refreshtok")
    assert out["access_token"] == "NEWTOK"
    assert c.access_token == "NEWTOK"          # client updates its own token
    assert seen["method"] == "POST"
    assert seen["path"] == "/session/refresh_token"
    f = seen["form"]
    assert f["api_key"] == "ak"
    assert f["refresh_token"] == "refreshtok"
    assert len(f["checksum"]) == 64            # sha256 hex digest


# ─── Portfolio: auctions + holdings authorisation ────────────────────────────
async def test_get_auctions_reads_auction_list():
    handler, seen = _capture([{"auction_number": "1", "tradingsymbol": "INFY"}])
    c = _client(handler)
    out = await c.get_auctions()
    assert seen["method"] == "GET"
    assert seen["path"] == "/portfolio/holdings/auctions"
    assert out[0]["tradingsymbol"] == "INFY"


async def test_get_auctions_without_session_never_hits_the_network():
    """A LIVE client with no token must not answer "[]" — that is a fabricated fact
    about the account. It raises instead, and still makes no request. Paper mode has no
    session by design, so there the stub IS the honest answer."""
    async def boom(request):
        raise AssertionError("network hit without a session")
    c = _client(boom)
    c._access_token = ""
    with pytest.raises(KiteTokenError):
        await c.get_auctions()

    paper = _client(boom, is_paper=True)
    paper._access_token = ""
    assert await paper.get_auctions() == []


async def test_initiate_holdings_auth_posts_isin_quantity():
    handler, seen = _capture({"request_id": "REQ123"})
    c = _client(handler)
    out = await c.initiate_holdings_auth([{"isin": "INE002A01018", "quantity": 5}])
    assert out["request_id"] == "REQ123"
    assert seen["method"] == "POST"
    assert seen["path"] == "/portfolio/holdings/authorise"
    qm = parse_qs(seen["raw"])
    assert qm["isin"] == ["INE002A01018"]
    assert qm["quantity"] == ["5"]


async def test_initiate_holdings_auth_no_instruments():
    handler, seen = _capture({"request_id": "REQ0"})
    c = _client(handler)
    out = await c.initiate_holdings_auth()
    assert out["request_id"] == "REQ0"
    assert seen["path"] == "/portfolio/holdings/authorise"


# ─── Mutual funds: order/SIP lifecycle + instruments ─────────────────────────
async def test_get_mf_order_by_id():
    handler, seen = _capture({"order_id": "MF1", "status": "COMPLETE"})
    c = _client(handler)
    out = await c.get_mf_order("MF1")
    assert seen["path"] == "/mf/orders/MF1"
    assert out["status"] == "COMPLETE"


async def test_place_mf_sip_payload():
    handler, seen = _capture({"sip_id": "SIP1"})
    c = _client(handler)
    out = await c.place_mf_sip(tradingsymbol="INF209K01XI3", amount=1000,
                               instalments=12, frequency="monthly")
    assert out["sip_id"] == "SIP1"
    assert seen["method"] == "POST"
    assert seen["path"] == "/mf/sips"
    f = seen["form"]
    assert f["tradingsymbol"] == "INF209K01XI3"
    assert f["amount"] == "1000"
    assert f["instalments"] == "12"
    assert f["frequency"] == "monthly"


async def test_place_mf_sip_paper_no_network():
    async def boom(request):
        raise AssertionError("network hit in paper mode")
    c = _client(boom, is_paper=True)
    out = await c.place_mf_sip(tradingsymbol="X", amount=500, instalments=6, frequency="monthly")
    assert out["sip_id"].startswith("PAPER-SIP-")


async def test_get_mf_sip_by_id():
    handler, seen = _capture({"sip_id": "SIP1", "status": "ACTIVE"})
    c = _client(handler)
    out = await c.get_mf_sip("SIP1")
    assert seen["path"] == "/mf/sips/SIP1"
    assert out["status"] == "ACTIVE"


async def test_modify_mf_sip_puts_changed_fields():
    handler, seen = _capture({"sip_id": "SIP1"})
    c = _client(handler)
    await c.modify_mf_sip("SIP1", amount=2000, status="paused")
    assert seen["method"] == "PUT"
    assert seen["path"] == "/mf/sips/SIP1"
    f = seen["form"]
    assert f["amount"] == "2000"
    assert f["status"] == "paused"


async def test_cancel_mf_sip_deletes():
    handler, seen = _capture({"sip_id": "SIP1"})
    c = _client(handler)
    await c.cancel_mf_sip("SIP1")
    assert seen["method"] == "DELETE"
    assert seen["path"] == "/mf/sips/SIP1"


async def test_cancel_mf_sip_paper_no_network():
    async def boom(request):
        raise AssertionError("network hit in paper mode")
    c = _client(boom, is_paper=True)
    out = await c.cancel_mf_sip("SIP1")
    assert out["sip_id"] == "SIP1"


async def test_search_mf_instruments_parses_csv():
    csv = (
        "tradingsymbol,amc,name,scheme_type,plan,last_price\n"
        "INF209K01XI3,Aditya Birla,ABSL Frontline Equity,Equity,Direct,350.5\n"
        "INF179K01XQ0,HDFC,HDFC Liquid Fund,Debt,Direct,4800.0\n"
    )
    handler, seen = _capture(text=csv)
    c = _client(handler)
    rows = await c.search_mf_instruments("frontline", limit=10)
    assert seen["path"] == "/mf/instruments"
    assert len(rows) == 1
    assert rows[0]["tradingsymbol"] == "INF209K01XI3"
    assert rows[0]["last_price"] == 350.5


# ─── Alerts API ──────────────────────────────────────────────────────────────
async def test_get_alerts_without_session_never_hits_the_network():
    async def boom(request):
        raise AssertionError("network hit without a session")
    c = _client(boom)
    c._access_token = ""
    with pytest.raises(KiteTokenError):
        await c.get_alerts()

    paper = _client(boom, is_paper=True)
    paper._access_token = ""
    assert await paper.get_alerts() == []


async def test_get_alerts_reads_list():
    handler, seen = _capture([{"uuid": "u1", "name": "INFY > 1500"}])
    c = _client(handler)
    out = await c.get_alerts()
    assert seen["method"] == "GET"
    assert seen["path"] == "/alerts"
    assert out[0]["uuid"] == "u1"


async def test_create_alert_simple_constant_payload():
    handler, seen = _capture({"uuid": "u1"})
    c = _client(handler)
    out = await c.create_alert(
        name="INFY above 1500", lhs_exchange="NSE", lhs_tradingsymbol="INFY",
        lhs_attribute="LastTradedPrice", operator=">=", rhs_constant=1500,
    )
    assert out["uuid"] == "u1"
    assert seen["method"] == "POST"
    assert seen["path"] == "/alerts"
    f = seen["form"]
    assert f["name"] == "INFY above 1500"
    assert f["type"] == K.ALERT_TYPE_SIMPLE
    assert f["lhs_exchange"] == "NSE"
    assert f["lhs_tradingsymbol"] == "INFY"
    assert f["lhs_attribute"] == "LastTradedPrice"
    assert f["operator"] == ">="
    assert f["rhs_type"] == "constant"
    assert f["rhs_constant"] == "1500"


async def test_get_alert_by_uuid():
    handler, seen = _capture({"uuid": "u1", "name": "X"})
    c = _client(handler)
    out = await c.get_alert("u1")
    assert seen["path"] == "/alerts/u1"
    assert out["uuid"] == "u1"


async def test_get_alert_history():
    handler, seen = _capture([{"uuid": "u1", "triggered_at": "2026-06-13 10:00:00"}])
    c = _client(handler)
    out = await c.get_alert_history("u1")
    assert seen["path"] == "/alerts/u1/history"
    assert out[0]["uuid"] == "u1"


async def test_modify_alert_puts_changes():
    handler, seen = _capture({"uuid": "u1"})
    c = _client(handler)
    await c.modify_alert("u1", name="renamed", operator="<=", rhs_constant=1400)
    assert seen["method"] == "PUT"
    assert seen["path"] == "/alerts/u1"
    f = seen["form"]
    assert f["name"] == "renamed"
    assert f["operator"] == "<="
    assert f["rhs_constant"] == "1400"


async def test_delete_alerts_passes_repeated_uuid_params():
    handler, seen = _capture({})
    c = _client(handler)
    await c.delete_alerts(["u1", "u2"])
    assert seen["method"] == "DELETE"
    assert seen["path"] == "/alerts"
    assert seen["query_multi"]["uuid"] == ["u1", "u2"]


async def test_create_ato_alert_sends_basket_json():
    handler, seen = _capture({"uuid": "u1"})
    c = _client(handler)
    await c.create_alert(
        name="auto-buy INFY dip", lhs_exchange="NSE", lhs_tradingsymbol="INFY",
        lhs_attribute="LastTradedPrice", operator="<=", rhs_constant=1400,
        alert_type=K.ALERT_TYPE_ATO,
        basket=[{"exchange": "NSE", "tradingsymbol": "INFY", "transaction_type": "BUY",
                 "quantity": 1, "order_type": "MARKET", "product": "CNC"}],
    )
    f = seen["form"]
    assert f["type"] == K.ALERT_TYPE_ATO
    basket = json.loads(f["basket"])
    assert basket[0]["tradingsymbol"] == "INFY"
    assert basket[0]["transaction_type"] == "BUY"


async def test_create_ato_alert_paper_is_simulated_no_network():
    async def boom(request):  # an ATO alert arms real orders → must not reach Kite in paper
        raise AssertionError("network hit creating an ATO alert in paper mode")
    c = _client(boom, is_paper=True)
    out = await c.create_alert(
        name="x", lhs_exchange="NSE", lhs_tradingsymbol="INFY",
        lhs_attribute="LastTradedPrice", operator="<=", rhs_constant=1400,
        alert_type=K.ALERT_TYPE_ATO, basket=[{"tradingsymbol": "INFY"}],
    )
    assert out["uuid"].startswith("PAPER-ATO-")


async def test_create_simple_alert_paper_still_calls_api():
    # simple alerts are notifications (no market impact) → real even on paper accounts
    handler, seen = _capture({"uuid": "u9"})
    c = _client(handler, is_paper=True)
    out = await c.create_alert(
        name="notify", lhs_exchange="NSE", lhs_tradingsymbol="INFY",
        lhs_attribute="LastTradedPrice", operator=">=", rhs_constant=1500,
    )
    assert out["uuid"] == "u9"
    assert seen["path"] == "/alerts"
