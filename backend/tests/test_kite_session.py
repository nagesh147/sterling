"""Kite session/login helpers + generate_session network flow."""
import hashlib

import httpx
import pytest

from app.services.exchanges.kite import session
from app.services.exchanges.kite.client import KiteClient


def test_login_url_contains_api_key_and_version():
    url = session.login_url("MYKEY")
    assert "api_key=MYKEY" in url
    assert "v=3" in url
    assert url.startswith("https://kite.zerodha.com/connect/login")


def test_checksum_is_sha256_of_concatenation():
    cs = session.checksum("ak", "rt", "sec")
    assert cs == hashlib.sha256(b"akrtsec").hexdigest()
    assert len(cs) == 64


def _mock_client(handler):
    c = KiteClient(api_key="ak", api_secret="sec", access_token="", is_paper=False)
    c._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.kite.trade",
        headers={"X-Kite-Version": "3"},
    )
    return c


async def test_generate_session_posts_checksum_and_sets_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        from urllib.parse import parse_qs
        seen["form"] = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        return httpx.Response(200, json={
            "status": "success",
            "data": {"access_token": "ATOKEN", "user_id": "AB1234", "user_name": "Trader"},
        })

    c = _mock_client(handler)
    data = await c.generate_session("reqtok")

    assert seen["path"] == "/session/token"
    assert seen["form"]["api_key"] == "ak"
    assert seen["form"]["request_token"] == "reqtok"
    assert seen["form"]["checksum"] == hashlib.sha256(b"akreqtoksec").hexdigest()
    assert data["access_token"] == "ATOKEN"
    assert c.access_token == "ATOKEN"  # captured for subsequent calls


async def test_generate_session_requires_key_and_secret():
    c = KiteClient(api_key="", api_secret="", is_paper=False)
    with pytest.raises(Exception):
        await c.generate_session("reqtok")
