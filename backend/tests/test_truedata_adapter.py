import httpx
import pytest

from app.services.market_data.truedata import TrueDataHistoricalClient, TrueDataNoDataError


@pytest.mark.asyncio
async def test_authentication_uses_documented_form_fields():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "access_token": "token-1",
                "token_type": "bearer",
                "expires_in": 3600,
            },
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TrueDataHistoricalClient("user", "secret", client=client)
    token = await adapter.authenticate()
    await client.aclose()

    assert token.access_token == "token-1"
    assert seen["method"] == "POST"
    assert "username=user" in seen["body"]
    assert "password=secret" in seen["body"]
    assert "grant_type=passoword" in seen["body"]


@pytest.mark.asyncio
async def test_get_ticks_uses_documented_history_contract():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        if request.url.path.endswith("/token"):
            return httpx.Response(
                200,
                json={"access_token": "token-1", "token_type": "bearer", "expires_in": 3600},
                request=request,
            )
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            text="timestamp,ltp,volume,oi\n2026-08-12T09:15:00,100.5,20,3\n",
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TrueDataHistoricalClient("user", "secret", client=client)
    rows = await adapter.get_ticks("NIFTY-I", "260812T09:15:00", "260812T09:30:00")
    await client.aclose()

    assert rows == [{"timestamp": "2026-08-12T09:15:00", "ltp": "100.5", "volume": "20", "oi": "3"}]
    assert "symbol=NIFTY-I" in seen["url"]
    assert "bidask=0" in seen["url"]
    assert "from=260812T09%3A15%3A00" in seen["url"]
    assert "to=260812T09%3A30%3A00" in seen["url"]
    assert "response=csv" in seen["url"]
    assert seen["authorization"] == "bearer token-1"


@pytest.mark.asyncio
async def test_get_bars_uses_documented_history_contract():
    seen = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        if request.url.path.endswith("/token"):
            return httpx.Response(
                200,
                json={"access_token": "token-1", "token_type": "bearer", "expires_in": 3600},
                request=request,
            )
        return httpx.Response(
            200,
            text="timestamp,open,high,low,close,volume,oi\n2026-08-12T09:15:00,100,101,99,100.5,20,3\n",
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TrueDataHistoricalClient("user", "secret", client=client)
    rows = await adapter.get_bars("NIFTY-I", "260812T09:15:00", "260812T09:30:00", interval="1min")
    await client.aclose()

    assert rows == [{
        "timestamp": "2026-08-12T09:15:00",
        "open": "100",
        "high": "101",
        "low": "99",
        "close": "100.5",
        "volume": "20",
        "oi": "3",
    }]
    assert "/getbars" in seen["url"]
    assert "symbol=NIFTY-I" in seen["url"]
    assert "interval=1min" in seen["url"]
    assert "response=csv" in seen["url"]


@pytest.mark.asyncio
async def test_get_bars_rejects_undocumented_interval():
    adapter = TrueDataHistoricalClient(
        "user",
        "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
    )
    with pytest.raises(ValueError, match="bar intervals"):
        await adapter.get_bars("NIFTY-I", "260812T09:15:00", "260812T09:30:00", interval="4min")
    await adapter.aclose()


@pytest.mark.asyncio
async def test_last_bars_enforces_documented_bounds_and_bidask():
    adapter = TrueDataHistoricalClient(
        "user",
        "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
    )
    with pytest.raises(ValueError, match="1..200"):
        await adapter.get_last_bars("NIFTY-I", 201)
    with pytest.raises(ValueError, match="bidask=0"):
        await adapter.get_last_bars("NIFTY-I", 10, bidask=1)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_last_ticks_rejects_more_than_documented_maximum():
    adapter = TrueDataHistoricalClient(
        "user",
        "secret",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))),
    )
    with pytest.raises(ValueError, match="1..200"):
        await adapter.get_last_ticks("NIFTY-I", 201)
    await adapter.aclose()


@pytest.mark.asyncio
async def test_no_data_is_explicit():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            return httpx.Response(
                200,
                json={"access_token": "token-1", "token_type": "bearer", "expires_in": 3600},
                request=request,
            )
        return httpx.Response(200, text="No Data exists for NIFTY-I", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = TrueDataHistoricalClient("user", "secret", client=client)
    with pytest.raises(TrueDataNoDataError):
        await adapter.get_ticks("NIFTY-I", "260812T09:15:00", "260812T09:30:00")
    await client.aclose()
