"""The auto-execute gate, over a real HTTP round-trip.

``autoexec_preflight`` was covered by unit tests and ``_gate_autoexec`` by direct
calls to the endpoint functions, but nothing exercised the route itself. That left
the part you actually rely on unproven: that the 409 reaches the client at all, that
its ``reasons`` survive serialisation (the detail is a dict, not a string), that
``force`` binds from the query string, and that the gate is not accidentally applied
to turning auto-execute OFF.

Every test here drives ``/api/v1/kite/engine/config`` through TestClient.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine import positions, state
from main import create_app

UID = "gate-http"
HEADERS = {"X-User-Id": UID}
URL = "/api/v1/kite/engine/config"


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean():
    state.reset(UID)
    positions.reset(UID)
    state.set_config(UID, EngineConfigModel(auto_execute=False))
    yield
    state.reset(UID)
    positions.reset(UID)


def _unprotected_position():
    """An OPEN position with no stop — nothing will exit it on price."""
    positions.register(positions.OpenPosition(
        uid=UID, symbol="NIFTY24JUN24000CE", exchange="NFO", token=777,
        qty=75, entry_premium=120.0, stop_premium=0.0, order_id="ENTRY-1",
        status=positions.OPEN, direction="long",
        red_count_ms=int(time.time() * 1000)))


def test_post_refuses_to_arm_auto_execute_over_an_unguarded_book(client):
    _unprotected_position()
    body = EngineConfigModel(auto_execute=True).model_dump(mode="json")

    r = client.post(URL, headers=HEADERS, json=body)

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "auto_execute_blocked"
    assert any("NO stop" in reason for reason in detail["reasons"]), detail
    assert state.get_config(UID).auto_execute is False, "and it did not take effect"


def test_patch_refuses_the_same_way(client):
    _unprotected_position()

    r = client.patch(URL, headers=HEADERS, json={"auto_execute": True})

    assert r.status_code == 409, r.text
    assert r.json()["detail"]["reasons"], "the reasons must survive serialisation"
    assert state.get_config(UID).auto_execute is False


def test_force_overrides_the_gate(client):
    """A gate, not a prohibition — the reasons are returned so the choice is informed."""
    _unprotected_position()

    r = client.patch(f"{URL}?force=true", headers=HEADERS, json={"auto_execute": True})

    assert r.status_code == 200, r.text
    assert r.json()["auto_execute"] is True
    assert state.get_config(UID).auto_execute is True


def test_turning_auto_execute_off_is_never_gated(client):
    """The book is in exactly the state that blocks arming; standing down must always
    be allowed, or the gate would trap the user in the position it is warning about."""
    state.set_config(UID, EngineConfigModel(auto_execute=True))
    _unprotected_position()

    r = client.patch(URL, headers=HEADERS, json={"auto_execute": False})

    assert r.status_code == 200, r.text
    assert r.json()["auto_execute"] is False


def test_an_unrelated_write_is_not_gated_while_auto_execute_stays_on(client):
    """The gate fires on the OFF→ON transition only. Re-asserting an already-on
    auto_execute while changing something else must not start failing."""
    state.set_config(UID, EngineConfigModel(auto_execute=True))
    _unprotected_position()

    r = client.patch(URL, headers=HEADERS, json={"max_lots": 4})

    assert r.status_code == 200, r.text
    assert r.json()["max_lots"] == 4
    assert r.json()["auto_execute"] is True


def test_a_clean_book_arms_without_complaint(client):
    r = client.patch(URL, headers=HEADERS, json={"auto_execute": True})

    assert r.status_code == 200, r.text
    assert r.json()["auto_execute"] is True


def test_a_stuck_pending_entry_also_blocks(client):
    """We do not know whether it filled, so we do not know what we are carrying."""
    positions.register(positions.OpenPosition(
        uid=UID, symbol="NIFTY24JUN24100CE", exchange="NFO", token=778,
        qty=75, entry_premium=100.0, stop_premium=80.0, order_id="ENTRY-2",
        status=positions.PENDING, direction="long",
        opened_ms=int(time.time() * 1000) - 86_400_000))   # a day old

    r = client.patch(URL, headers=HEADERS, json={"auto_execute": True})

    assert r.status_code == 409, r.text
    assert any("PENDING" in reason for reason in r.json()["detail"]["reasons"])
