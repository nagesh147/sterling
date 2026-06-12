"""Kite order/GTT payload mapping + paper-mode + contract edge cases."""
from urllib.parse import parse_qs

import httpx
import pytest

from app.services.exchanges.kite import constants as K
from app.services.exchanges.kite.client import KiteClient
from app.services.exchanges.kite.errors import KiteOrderError


def _client(handler, *, is_paper=False):
    c = KiteClient(api_key="ak", api_secret="sec", access_token="tok", is_paper=is_paper)
    c._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.kite.trade",
        headers={"X-Kite-Version": "3"},
    )
    return c


def _capture():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["query"] = dict(request.url.params)
        body = request.content.decode() if request.content else ""
        seen["form"] = {k: v[0] for k, v in parse_qs(body).items()} if body else {}
        seen["ctype"] = request.headers.get("content-type", "")
        return httpx.Response(200, json={"status": "success", "data": {"order_id": "ORD1"}})

    return handler, seen


async def test_place_order_market_payload():
    handler, seen = _capture()
    c = _client(handler)
    out = await c.place_order("NSE:INFY", "buy", 10, product=K.PRODUCT_CNC)
    assert out["order_id"] == "ORD1"
    assert seen["method"] == "POST"
    assert seen["path"] == "/orders/regular"
    assert "application/x-www-form-urlencoded" in seen["ctype"]
    f = seen["form"]
    assert f["exchange"] == "NSE"
    assert f["tradingsymbol"] == "INFY"
    assert f["transaction_type"] == "BUY"
    assert f["quantity"] == "10"
    assert f["order_type"] == "MARKET"
    assert f["product"] == "CNC"
    assert "price" not in f  # market order carries no price


async def test_place_order_limit_payload():
    handler, seen = _capture()
    c = _client(handler)
    await c.place_order("NSE:INFY", "sell", 5, order_type="limit_order", limit_price=1499.5)
    f = seen["form"]
    assert f["order_type"] == "LIMIT"
    assert f["transaction_type"] == "SELL"
    assert f["price"] == "1499.5"
    assert f["validity"] == "DAY"


async def test_place_order_stoploss_trigger():
    handler, seen = _capture()
    c = _client(handler)
    await c.place_order("NSE:INFY", "sell", 5, kite_order_type="SL-M", trigger_price=1400)
    f = seen["form"]
    assert f["order_type"] == "SL-M"
    assert f["trigger_price"] == "1400"


async def test_place_order_paper_returns_mock_without_network():
    async def boom(request):  # must never be called in paper mode
        raise AssertionError("network hit in paper mode")
    c = _client(boom, is_paper=True)
    out = await c.place_order("NSE:INFY", "buy", 1)
    assert out["order_id"].startswith("PAPER-")


async def test_post_only_rejected():
    handler, _ = _capture()
    c = _client(handler)
    with pytest.raises(KiteOrderError):
        await c.place_order("NSE:INFY", "buy", 1, post_only=True)


async def test_cancel_order_uses_variety_ignores_product_id():
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["path"] = request.url.path
        return httpx.Response(200, json={"status": "success", "data": {"order_id": "ORD1"}})

    c = _client(handler)
    await c.cancel_order("ORD1", 999, variety="amo")
    assert seen["method"] == "DELETE"
    assert seen["path"] == "/orders/amo/ORD1"


async def test_place_gtt_encodes_condition_and_orders_as_json():
    handler, seen = _capture()
    c = _client(handler)
    await c.place_gtt(
        trigger_type="single", tradingsymbol="INFY", exchange="NSE",
        last_price=1500, trigger_values=[1450],
        orders=[{"tradingsymbol": "INFY", "transaction_type": "SELL"}],
    )
    f = seen["form"]
    assert seen["path"] == "/gtt/triggers"
    assert f["type"] == "single"
    import json
    cond = json.loads(f["condition"])
    assert cond["trigger_values"] == [1450]
    assert cond["tradingsymbol"] == "INFY"
    orders = json.loads(f["orders"])
    assert orders[0]["transaction_type"] == "SELL"


async def test_order_margins_posts_json_array():
    seen = {}

    def handler(request):
        seen["ctype"] = request.headers.get("content-type", "")
        import json
        seen["json"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"status": "success", "data": [{"total": 123.0}]})

    c = _client(handler)
    res = await c.order_margins([{"exchange": "NSE", "tradingsymbol": "INFY"}])
    assert "application/json" in seen["ctype"]
    assert seen["json"][0]["tradingsymbol"] == "INFY"
    assert res[0]["total"] == 123.0
