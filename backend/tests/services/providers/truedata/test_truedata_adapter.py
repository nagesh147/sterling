"""Tests for TrueData adapter, timestamp causality, malformed responses, token expiry, and WebSocket stream manager."""
import time
import pytest
from httpx import AsyncClient, MockTransport, Response

from app.services.market_data.truedata import (
    TrueDataAuthError,
    TrueDataError,
    TrueDataHistoricalClient,
)
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter
from app.services.providers.truedata.ws_client import (
    SingleStreamConflictError,
    TrueDataStreamManager,
)


# --- TrueData Adapter Mapping & Causality Tests ---


def test_bar_event_mapping_and_causality():
    raw_bar = {
        "timestamp": "2026-08-14 12:00:00",
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 102.5,
        "volume": 1500,
        "oi": 500,
    }
    event = TrueDataMarketDataAdapter.create_bar_event(
        "NIFTY26AUGFUT",
        raw_bar,
        receipt_time_iso="2026-08-14T12:00:01+00:00",
        sequence=42,
    )

    assert event.event_type == "bar"
    assert event.instrument_id == "NIFTY26AUGFUT"
    assert event.event_time == "2026-08-14T06:30:00+00:00"
    assert event.available_at == "2026-08-14T12:00:01+00:00"
    assert event.available_at >= event.event_time  # Causal invariant
    assert event.source == "truedata"
    assert event.source_version == "2.6"
    assert event.payload["open"] == 100.0
    assert event.payload["close"] == 102.5
    assert event.sequence == 42


def test_available_at_cannot_precede_event_time():
    raw_bar = {"timestamp": "2026-08-14 12:00:00", "open": 100, "high": 100, "low": 100, "close": 100}

    # Pass receipt time earlier than event time
    event = TrueDataMarketDataAdapter.create_bar_event(
        "NIFTY", raw_bar, receipt_time_iso="2026-08-14T11:59:59+00:00"
    )

    # Adapter auto-adjusts available_at to match event_time so available_at >= event_time
    assert event.available_at >= event.event_time


def test_malformed_timestamp_raises_value_error():
    raw_bar = {"timestamp": "invalid-timestamp", "open": 100.0}
    with pytest.raises(ValueError, match="Invalid TrueData timestamp"):
        TrueDataMarketDataAdapter.create_bar_event("NIFTY", raw_bar)


# --- Token Expiry & Automated Re-Authentication Tests ---


@pytest.mark.asyncio
async def test_token_expiration_triggers_reauthentication():
    auth_calls = 0

    def handler(request):
        nonlocal auth_calls
        if request.url.path == "/token":
            auth_calls += 1
            return Response(
                200,
                json={
                    "access_token": f"token_v{auth_calls}",
                    "token_type": "bearer",
                    "expires_in": 1,  # 1 second TTL
                },
            )
        elif request.url.path == "/getbars":
            auth_header = request.headers.get("Authorization")
            if auth_header != f"bearer token_v{auth_calls}":
                return Response(401, json={"error": "invalid_token"})
            return Response(
                200,
                text="timestamp, open, high, low, close, volume, oi\n2026-08-14 12:00:00, 100, 105, 95, 102, 500, 100\n",
            )
        return Response(404)

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)

    # First call authenticates (token_v1)
    bars1 = await client.get_bars("NIFTY", "2026-08-14", "2026-08-14")
    assert len(bars1) == 1
    assert auth_calls == 1

    # Simulate token expiration by rewiring expires_at
    client._token = client._token.__class__(
        access_token=client._token.access_token,
        token_type=client._token.token_type,
        expires_at=time.time() - 10,
    )

    # Second call detects expired token and re-authenticates (token_v2)
    bars2 = await client.get_bars("NIFTY", "2026-08-14", "2026-08-14")
    assert len(bars2) == 1
    assert auth_calls == 2


@pytest.mark.asyncio
async def test_malformed_json_response_handling():
    def handler(request):
        return Response(200, text="Not a JSON object")

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)

    with pytest.raises(TrueDataError, match="non-JSON response"):
        await client.authenticate()


# --- Grant Type Fallback Unit Tests ---


@pytest.mark.asyncio
async def test_documented_grant_type_succeeds_without_fallback():
    calls = []

    def handler(request):
        calls.append(request)
        return Response(
            200, json={"access_token": "valid_token_123", "token_type": "bearer", "expires_in": 3600}
        )

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)
    token = await client.authenticate()

    assert token.access_token == "valid_token_123"
    assert len(calls) == 1
    assert "grant_type=passoword" in calls[0].content.decode()


@pytest.mark.asyncio
async def test_unsupported_grant_type_triggers_password_retry_and_succeeds():
    calls = []

    def handler(request):
        calls.append(request)
        body = request.content.decode()
        if "grant_type=passoword" in body:
            return Response(400, json={"error": "unsupported_grant_type"})
        elif "grant_type=password" in body:
            return Response(
                200, json={"access_token": "valid_token_456", "token_type": "bearer", "expires_in": 3600}
            )
        return Response(400)

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)
    token = await client.authenticate()

    assert token.access_token == "valid_token_456"
    assert len(calls) == 2
    assert "grant_type=passoword" in calls[0].content.decode()
    assert "grant_type=password" in calls[1].content.decode()


@pytest.mark.asyncio
async def test_unsupported_grant_type_password_retry_fails_surfaces_error():
    calls = []

    def handler(request):
        calls.append(request)
        body = request.content.decode()
        if "grant_type=passoword" in body:
            return Response(400, json={"error": "unsupported_grant_type"})
        elif "grant_type=password" in body:
            return Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "The user name or password is incorrect",
                },
            )
        return Response(400)

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)

    with pytest.raises(TrueDataAuthError, match="The user name or password is incorrect"):
        await client.authenticate()

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_no_retry_on_invalid_grant():
    calls = []

    def handler(request):
        calls.append(request)
        return Response(
            400, json={"error": "invalid_grant", "error_description": "Invalid credentials"}
        )

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)

    with pytest.raises(TrueDataAuthError, match="Invalid credentials"):
        await client.authenticate()

    assert len(calls) == 1  # No secondary request attempted


@pytest.mark.asyncio
async def test_no_retry_on_server_5xx_error():
    calls = []

    def handler(request):
        calls.append(request)
        return Response(500, json={"error": "internal_server_error", "error_description": "Server Fault"})

    async_client = AsyncClient(transport=MockTransport(handler))
    client = TrueDataHistoricalClient("user", "pwd", client=async_client)

    with pytest.raises(TrueDataError, match="Server Fault"):
        await client.authenticate()

    assert len(calls) == 1  # No secondary request attempted


# --- TrueData Single Stream Constraint Tests ---


@pytest.mark.asyncio
async def test_single_active_websocket_stream_constraint():
    manager = TrueDataStreamManager()

    # First connection succeeds
    c1 = await manager.connect_realtime("user1", "td_user_1")
    assert c1.active is True

    # Second connection for same user raises conflict error
    with pytest.raises(SingleStreamConflictError, match="Only one active connection is permitted"):
        await manager.connect_realtime("user1", "td_user_1")

    # Disconnect releases state
    await manager.disconnect("user1")
    assert c1.active is False

    # Connection after disconnect succeeds
    c2 = await manager.connect_realtime("user1", "td_user_1")
    assert c2.active is True
