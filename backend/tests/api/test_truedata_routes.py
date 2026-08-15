"""API route registration and flow tests for `/api/v1/truedata/*`."""
from __future__ import annotations

import os
import tempfile
import httpx
import pytest

from app.core.security import decrypt
from app.services import db
from app.services.providers import truedata as truedata_service


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    truedata_service.clear()
    yield
    truedata_service.clear()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
async def client():
    from main import create_app
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.asyncio
async def test_truedata_routes_are_registered_and_reachable(client):
    # 1. GET status
    resp_status = await client.get("/api/v1/truedata/status")
    assert resp_status.status_code == 200
    data_status = resp_status.json()
    assert "connected" in data_status
    assert "is_active" in data_status

    # 2. GET credentials (initially empty)
    resp_list = await client.get("/api/v1/truedata/credentials")
    assert resp_list.status_code == 200
    assert resp_list.json() == []

    # 3. POST credentials (create)
    resp_create = await client.post(
        "/api/v1/truedata/credentials",
        json={
            "label": "Test Feed",
            "username": "td_user_999",
            "password": "secret_password_123",
            "realtime_port": 8082,
        },
    )
    assert resp_create.status_code == 200
    created = resp_create.json()
    assert created["id"].startswith("TD-")
    assert created["label"] == "Test Feed"
    assert created["username_hint"] == "td****99"
    assert "secret_password_123" not in str(created)  # Password redacted

    # 4. Verify DB persistence and Fernet encryption at rest
    acct = truedata_service.get("default", created["id"])
    assert acct is not None
    assert acct.password_enc != "secret_password_123"
    assert decrypt(acct.password_enc) == "secret_password_123"

    # 5. GET status after creation
    resp_status_after = await client.get("/api/v1/truedata/status")
    assert resp_status_after.status_code == 200
    status_after = resp_status_after.json()
    assert status_after["is_active"] is True
    assert status_after["username_hint"] == "td****99"


@pytest.mark.asyncio
async def test_truedata_settings_data_source_selection(client):
    # Default is truedata
    resp = await client.get("/api/v1/truedata/settings")
    assert resp.status_code == 200
    assert resp.json()["data_source"] == "truedata"

    # Update to zerodhakite
    resp_update = await client.post(
        "/api/v1/truedata/settings",
        json={"data_source": "zerodhakite"},
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["data_source"] == "zerodhakite"

    # Verify persisted
    resp_check = await client.get("/api/v1/truedata/settings")
    assert resp_check.status_code == 200
    assert resp_check.json()["data_source"] == "zerodhakite"
