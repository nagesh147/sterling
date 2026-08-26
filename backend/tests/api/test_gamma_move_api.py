"""The Gamma Move config routes.

The recurring bug class in this codebase is a UI that claims backend behaviour
the backend does not honour, so these tests are mostly about what the server
*publishes*: defaults, vocabularies, and the research-only list the UI greys out.
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


def test_descriptor_publishes_identity_and_calibration(client):
    body = client.get("/config/gamma-move").json()
    s = body["strategy"]
    assert s["id"] == "gamma_move"
    # Not proven, so the UI must never offer live.
    # Not validated — and deliberately NOT a lock. Paper/live has its own switch.
    assert s["validated"] is False
    assert "live_ready" not in s
    assert s["headline_finding"]
    assert set(s["calibrated_fields"]) >= {"level_proximity_pct", "min_oi_drop_pct",
                                           "volume_spike_mult", "min_price_gain_pct",
                                           "regime_multiplier"}
    # Each measured default carries what the measurement was, so the UI can show
    # provenance beside the control rather than asking the reader to trust it.
    for field in s["calibrated_fields"]:
        assert s["calibration"][field]


def test_defaults_are_the_calibrated_values(client):
    d = client.get("/config/gamma-move").json()["defaults"]
    assert d["level_proximity_pct"] == 1.0
    assert d["min_oi_drop_pct"] == 3.0
    assert d["volume_spike_mult"] == 2.5
    assert d["min_price_gain_pct"] == 2.0
    assert d["regime_multiplier"] == 2.0      # not the conventional 3.0
    assert d["enabled"] is True
    assert d["stop_mode"] == "both"
    assert "execution_mode" not in d


def test_vocabularies_cover_every_choice_field(client):
    v = client.get("/config/gamma-move").json()["vocabularies"]
    for key in ("level_timeframe", "trigger_timeframe", "exit_policy", "stop_basis",
                "sizing_mode", "stop_mode", "scan_stocks"):
        assert v[key], f"{key} has no published vocabulary"


def test_the_eligible_universe_is_published(client):
    """So the UI's selectable set cannot drift from what the scanner accepts."""
    from app.services.kite_engine.stock_registry import HIGH_LIQUIDITY_STOCK_NAMES
    v = client.get("/config/gamma-move").json()["vocabularies"]
    assert set(v["scan_stocks"]) == set(HIGH_LIQUIDITY_STOCK_NAMES)


def test_an_off_registry_stock_is_refused(client):
    r = client.put("/config/gamma-move", json={"scan_stocks": ["SOMEPENNYCO"]})
    assert r.status_code == 422
    assert "registry" in r.json()["detail"]


def test_research_only_exits_are_published(client):
    """The source gives no exit rule, so only the time stop may run live."""
    r = client.get("/config/gamma-move").json()["research_only"]
    assert set(r["exit_policy"]) == {"PERCENT_TARGET", "TRAILING_STOP"}


def test_partial_update_changes_only_what_was_sent(client):
    before = client.get("/config/gamma-move").json()["config"]
    after = client.put("/config/gamma-move",
                       json={"min_oi_drop_pct": 4.5}).json()["config"]
    assert after["min_oi_drop_pct"] == 4.5
    assert after["volume_spike_mult"] == before["volume_spike_mult"]


def test_unknown_key_is_refused_not_dropped(client):
    """A silently ignored setting is worse than a 422: the UI cannot tell."""
    r = client.put("/config/gamma-move", json={"min_oi_drp_pct": 4.5})
    assert r.status_code == 422
    assert "min_oi_drp_pct" in r.json()["detail"]


def test_empty_body_is_refused(client):
    assert client.put("/config/gamma-move", json={}).status_code == 422


@pytest.mark.parametrize("payload,fragment", [
    ({"level_proximity_pct": 0}, "level_proximity_pct"),
    ({"min_oi_drop_pct": 0}, "min_oi_drop_pct"),
    ({"volume_spike_mult": 1.0}, "volume_spike_mult"),
    ({"max_days_to_expiry": 0}, "no limit"),
    ({"stop_percent": 100}, "100% stop"),
    ({"confirm_bars": 9}, "confirm_bars"),
])
def test_invalid_values_are_refused_with_a_reason(client, payload, fragment):
    r = client.put("/config/gamma-move", json=payload)
    assert r.status_code == 422
    assert fragment in r.json()["detail"]


def test_a_stop_is_required_regardless_of_mode(client):
    r = client.put("/config/gamma-move", json={"stop_percent": 0, "stop_points": 0})
    assert r.status_code == 422
    assert "a stop is required" in r.json()["detail"]


def test_warnings_are_published_for_risky_but_legal_choices(client):
    client.put("/config/gamma-move", json={"stop_mode": "monitor"})
    body = client.get("/config/gamma-move").json()
    assert any("unprotected" in w for w in body["warnings"])
    client.put("/config/gamma-move", json={"stop_mode": "both"})


def test_a_rejected_change_does_not_persist(client):
    client.put("/config/gamma-move", json={"min_oi_drop_pct": 3.0})
    client.put("/config/gamma-move", json={"min_oi_drop_pct": 0})
    assert client.get("/config/gamma-move").json()["config"]["min_oi_drop_pct"] == 3.0


def test_snapshot_states_that_the_strategy_is_unvalidated(client):
    """The finding belongs where the operator decides whether to switch it on,
    not only in a document."""
    body = client.get("/config/gamma-move/snapshot").json()
    assert any("not validated" in w for w in body["warnings"])


def test_snapshot_reports_mode_read_from_its_real_home(client):
    mode = client.get("/config/gamma-move/snapshot").json()["mode"]
    assert set(mode) >= {"is_paper", "auto_execute"}
    assert "Trading Mode" in mode["note"]


def test_arm_requires_a_signal_id(client):
    assert client.post("/config/gamma-move/arm", json={}).status_code == 422


def test_simulate_validates_its_arguments(client):
    assert client.post("/config/gamma-move/simulate", json={}).status_code == 422
    assert client.post("/config/gamma-move/simulate",
                       json={"symbols": ["X"], "days": 999}).status_code == 422
