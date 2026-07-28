"""Phase 5 API tests: `/api/v1/kite/navigator/*` (spec §15, §20.7)."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.services import db
from app.services.navigator import service as nav_service


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    nav_service.clear_cache("default")
    nav_service.clear_cache("user-a")
    nav_service.clear_cache("user-b")
    yield
    os.unlink(path)


@pytest.fixture
def client():
    from main import create_app
    return TestClient(create_app())


def _headers(uid: str) -> dict:
    return {"X-User-Id": uid}


class TestConfigEndpoints:
    def test_get_config_creates_disabled_default(self, client):
        resp = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["record"]["config"]["enabled"] is False
        assert body["record"]["revision"] == 1
        assert body["capabilities"]["engine_sources"] == ["kite_triple_supertrend"]

    def test_put_config_updates_and_increments_revision(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        cfg["flow_sample_seconds"] = 90
        resp = client.put(
            "/api/v1/kite/navigator/config",
            json={"config": cfg, "expected_revision": got["record"]["revision"]},
            headers=_headers("user-a"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["record"]["config"]["flow_sample_seconds"] == 90
        assert body["record"]["revision"] == 2

    def test_put_config_with_stale_revision_is_409(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": 1}, headers=_headers("user-a"))
        resp = client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": 1}, headers=_headers("user-a"))
        assert resp.status_code == 409
        assert "REVISION_CONFLICT" in resp.text

    def test_put_config_with_invalid_payload_is_400(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        cfg["fusion"]["base_weight"] = 999  # breaks weights-sum-to-100
        resp = client.put(
            "/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]},
            headers=_headers("user-a"),
        )
        assert resp.status_code == 400
        assert "INVALID_CONFIG" in resp.text

    def test_gate_mode_blocked_until_calibrated(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        cfg["enabled"] = True
        cfg["operating_mode"] = "gate"
        resp = client.put(
            "/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]},
            headers=_headers("user-a"),
        )
        assert resp.status_code == 423
        assert "GATE_NOT_CALIBRATED" in resp.text

    def test_validate_dry_run_does_not_persist(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        cfg["fusion"]["base_weight"] = 999
        resp = client.post("/api/v1/kite/navigator/config/validate", json=cfg, headers=_headers("user-a"))
        assert resp.status_code == 400
        after = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        assert after["record"]["revision"] == 1  # unaffected by the failed validate

    def test_reset_restores_disabled_defaults(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        cfg["enabled"] = True
        client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]}, headers=_headers("user-a"))
        resp = client.post("/api/v1/kite/navigator/config/reset", headers=_headers("user-a"))
        assert resp.status_code == 200
        assert resp.json()["record"]["config"]["enabled"] is False

    def test_users_are_isolated(self, client):
        got_a = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg_a = got_a["record"]["config"]
        cfg_a["flow_sample_seconds"] = 120
        client.put("/api/v1/kite/navigator/config", json={"config": cfg_a, "expected_revision": got_a["record"]["revision"]}, headers=_headers("user-a"))

        got_b = client.get("/api/v1/kite/navigator/config", headers=_headers("user-b")).json()
        assert got_b["record"]["config"]["flow_sample_seconds"] == 60  # untouched default


class TestStatusEndpoint:
    def test_status_reports_disabled_by_default(self, client):
        resp = client.get("/api/v1/kite/navigator/status", headers=_headers("user-a"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["health"] == "DISABLED"
        assert body["enabled"] is False


class TestSnapshotEndpoint:
    def test_snapshot_is_503_when_disabled(self, client):
        resp = client.get("/api/v1/kite/navigator/snapshot/NIFTY 50", headers=_headers("user-a"))
        assert resp.status_code == 503

    def test_snapshot_is_503_when_no_evidence_cached_yet(self, client):
        got = client.get("/api/v1/kite/navigator/config", headers=_headers("user-a")).json()
        cfg = got["record"]["config"]
        cfg["enabled"] = True
        client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]}, headers=_headers("user-a"))
        resp = client.get("/api/v1/kite/navigator/snapshot/NIFTY 50", headers=_headers("user-a"))
        assert resp.status_code == 503


class TestSignalsEndpoints:
    def test_list_signals_empty_by_default(self, client):
        resp = client.get("/api/v1/kite/navigator/signals", headers=_headers("user-a"))
        assert resp.status_code == 200
        assert resp.json()["decisions"] == []

    def test_get_unknown_signal_is_404(self, client):
        resp = client.get("/api/v1/kite/navigator/signals/does-not-exist", headers=_headers("user-a"))
        assert resp.status_code == 404

    def test_series_endpoint_returns_empty_points_by_default(self, client):
        resp = client.get("/api/v1/kite/navigator/series/NIFTY 50", headers=_headers("user-a"))
        assert resp.status_code == 200
        assert resp.json()["points"] == []


class TestCalibrationEndpoint:
    def test_calibration_reports_not_ready_by_default(self, client):
        resp = client.get("/api/v1/kite/navigator/calibration", headers=_headers("user-a"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["calibration_readiness"] == "not_ready"
        assert body["latest_report"] is None


class TestDefaultUserFallback:
    def test_missing_header_uses_default_user(self, client):
        resp = client.get("/api/v1/kite/navigator/config")
        assert resp.status_code == 200
