"""Tests for TrueData credentials, security encryption, redaction, and environment fallback."""
import pytest
from app.core.security import decrypt
from app.services.providers import truedata as truedata_service


def test_add_credentials_encrypts_password_and_first_is_active():
    truedata_service.clear()
    a = truedata_service.add(
        "user1",
        truedata_service.TrueDataCredentialCreate(
            label="Main Feed", username="td_user_123", password="super_secret_password"
        ),
    )

    assert a.is_active is True
    assert a.username == "td_user_123"
    assert a.password == "super_secret_password"  # Property decrypts
    assert a.password_enc != "super_secret_password"  # Stored encrypted
    assert decrypt(a.password_enc) == "super_secret_password"


def test_to_response_redacts_password_and_masks_username():
    truedata_service.clear()
    a = truedata_service.add(
        "user1",
        truedata_service.TrueDataCredentialCreate(
            username="td_user_123", password="super_secret_password"
        ),
    )
    resp = truedata_service.to_response(a)
    dumped = resp.model_dump()

    assert "super_secret_password" not in str(dumped)
    assert dumped["username_hint"] == "td****23"
    assert dumped["has_credentials"] is True


def test_user_isolation():
    truedata_service.clear()
    a1 = truedata_service.add("user1", truedata_service.TrueDataCredentialCreate(username="u1", password="p1"))
    a2 = truedata_service.add("user2", truedata_service.TrueDataCredentialCreate(username="u2", password="p2"))

    assert len(truedata_service.list_credentials("user1")) == 1
    assert len(truedata_service.list_credentials("user2")) == 1
    assert truedata_service.get("user2", a1.id) is None


def test_update_credentials_reencrypts_password():
    truedata_service.clear()
    a = truedata_service.add("user1", truedata_service.TrueDataCredentialCreate(username="u1", password="p1"))
    updated = truedata_service.update("user1", a.id, truedata_service.TrueDataCredentialUpdate(password="new_p2"))

    assert updated.password == "new_p2"
    assert decrypt(updated.password_enc) == "new_p2"


def test_delete_promotes_next_credential_to_active():
    truedata_service.clear()
    a1 = truedata_service.add("user1", truedata_service.TrueDataCredentialCreate(username="u1", password="p1"))
    a2 = truedata_service.add("user1", truedata_service.TrueDataCredentialCreate(username="u2", password="p2"))

    assert truedata_service.get_active("user1").id == a1.id
    truedata_service.delete("user1", a1.id)
    assert truedata_service.get_active("user1").id == a2.id


def test_environment_variable_fallback(monkeypatch):
    truedata_service.clear()
    monkeypatch.setenv("TRUEDATA_USERNAME", "env_user")
    monkeypatch.setenv("TRUEDATA_PASSWORD", "env_pass")

    active = truedata_service.get_active("user_empty")
    assert active is not None
    assert active.username == "env_user"
    assert active.password == "env_pass"


def test_truedata_settings_and_status_endpoints():
    from starlette.testclient import TestClient
    from main import app

    client = TestClient(app)
    # GET settings
    r = client.get("/api/v1/truedata/settings")
    assert r.status_code == 200
    assert "data_source" in r.json()

    # POST settings
    r = client.post("/api/v1/truedata/settings", json={"data_source": "truedata"})
    assert r.status_code == 200
    assert r.json()["data_source"] == "truedata"

    # GET status
    r = client.get("/api/v1/truedata/status")
    assert r.status_code == 200
    assert "connected" in r.json()

