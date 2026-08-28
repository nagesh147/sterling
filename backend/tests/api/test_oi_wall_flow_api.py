"""The OI Wall Flow config routes.

The recurring bug class in this codebase is a UI that claims backend behaviour
the backend does not honour, so these tests are mostly about what the server
*publishes*: defaults, vocabularies, and that thresholds are judgement, not
calibration.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STERLING_DB_PATH", str(tmp_path / "test.db"))
    from app.services import db
    monkeypatch.setattr(db, "_DB_PATH", str(tmp_path / "test.db"), raising=False)
    db.init()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_descriptor_publishes_identity_and_judgement(client):
    body = client.get("/config/oi-wall-flow").json()
    s = body["strategy"]
    assert s["id"] == "oi_wall_flow"
    assert s["validated"] is False
    assert "live_ready" not in s
    assert s["headline_finding"]
    assert s["calibrated_fields"] == []
    assert "stop_premium_pct" in s["judgement_fields"]
    assert s["calibration"]["stop_premium_pct"]


def test_defaults_are_the_judgement_values(client):
    d = client.get("/config/oi-wall-flow").json()["defaults"]
    assert d["stop_premium_pct"] == 40.0
    assert d["target_premium_pct"] == 50.0
    assert d["min_bias_score"] == 3.0
    assert d["skip_atm"] is True
    assert d["enabled"] is True
    assert d["stop_mode"] == "both"
    assert "execution_mode" not in d
    assert d["scan_interval_seconds"] == 300


def test_vocabularies_cover_choice_fields(client):
    v = client.get("/config/oi-wall-flow").json()["vocabularies"]
    for key in ("stop_mode", "expiry_selection", "scan_stocks"):
        assert v[key], f"{key} has no published vocabulary"


def test_the_eligible_universe_is_published(client):
    from app.services.kite_engine.stock_registry import HIGH_LIQUIDITY_STOCK_NAMES
    v = client.get("/config/oi-wall-flow").json()["vocabularies"]
    assert set(v["scan_stocks"]) == set(HIGH_LIQUIDITY_STOCK_NAMES)


def test_an_off_registry_stock_is_refused(client):
    r = client.put("/config/oi-wall-flow", json={"scan_stocks": ["SOMEPENNYCO"]})
    assert r.status_code == 422
    assert "registry" in r.json()["detail"]


def test_unknown_key_is_refused(client):
    r = client.put("/config/oi-wall-flow", json={"not_a_field": 1})
    assert r.status_code == 422
    assert "not_a_field" in r.json()["detail"]


def test_empty_put_is_refused(client):
    r = client.put("/config/oi-wall-flow", json={})
    assert r.status_code == 422


def test_invalid_stop_is_refused(client):
    r = client.put("/config/oi-wall-flow", json={"stop_premium_pct": 0})
    assert r.status_code == 422
    assert "stop_premium_pct" in r.json()["detail"]


def test_rejected_change_does_not_persist(client):
    before = client.get("/config/oi-wall-flow").json()["config"]["lots"]
    client.put("/config/oi-wall-flow", json={"lots": 0})
    after = client.get("/config/oi-wall-flow").json()["config"]["lots"]
    assert after == before


def test_stop_mode_monitor_publishes_a_warning(client):
    r = client.put("/config/oi-wall-flow", json={"stop_mode": "monitor"})
    assert r.status_code == 200
    warnings = client.get("/config/oi-wall-flow").json()["warnings"]
    assert any("unprotected" in w for w in warnings)


def test_arm_without_signal_id_is_422(client):
    r = client.post("/config/oi-wall-flow/arm", json={},
                    headers={"X-User-Id": "u1"})
    assert r.status_code == 422


def test_bse_golden_still_arms_3500_ce():
    """The motivating chain must still arm 3500 CE after the live fields landed."""
    from tests.engines.oi_wall_flow.conftest import rows_from
    from app.engines.oi_wall_flow import ChainSnapshot, OIWallFlowConfig, OIWallFlowStrategy
    cfg = OIWallFlowConfig(max_premium_at_risk_inr=50_000).validate()
    snap = ChainSnapshot(underlying="BSE", spot=3392.50, expiry="2026-09-29",
                         rows=rows_from(), days_to_expiry=32, lot_size=200)
    sig = OIWallFlowStrategy(cfg).evaluate(snap)
    assert sig.state == "armed"
    assert sig.plan.option_type == "CE"
    assert sig.plan.strike == 3500
    assert sig.plan.entry == 84.15
