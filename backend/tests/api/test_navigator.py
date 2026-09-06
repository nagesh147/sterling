"""Phase 5 API tests: `/api/v1/kite/navigator/*` (spec §15, §20.7)."""
from __future__ import annotations

import os
import tempfile

import httpx
import pytest

from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineConfigModel, EngineSignalRow
from app.services import db
from app.services.kite_engine import state as kite_state
from app.services.navigator import service as nav_service
from app.services.navigator import config_store, runtime as nav_runtime


@pytest.fixture(autouse=True)
def isolated_db():
    # `db._DB_PATH` is module-global. Pointing it at a temp file without
    # restoring it leaves every LATER test in the session reading a database
    # that this fixture then deletes — which is how the replay test two files
    # away started seeing an empty candle/signal store and zero trades.
    prior_path = db._DB_PATH
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    nav_service.clear_cache("default")
    nav_service.clear_cache("user-a")
    nav_service.clear_cache("user-b")
    nav_runtime._snapshots.pop("user-a", None)
    kite_state.reset("user-a")
    try:
        yield
    finally:
        nav_runtime._snapshots.pop("user-a", None)
        kite_state.reset("user-a")
        db._DB_PATH = prior_path
        db.init()
        os.unlink(path)


@pytest.fixture
async def client():
    from main import create_app
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


def _headers(uid: str) -> dict:
    return {"X-User-Id": uid}


class TestConfigEndpoints:
    async def test_get_config_creates_disabled_default(self, client):
        resp = await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["record"]["config"]["enabled"] is False
        assert body["record"]["revision"] == 1
        assert body["capabilities"]["engine_sources"] == ["kite_triple_supertrend"]

    async def test_put_config_updates_and_increments_revision(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        cfg["flow_sample_seconds"] = 90
        resp = await client.put(
            "/api/v1/kite/navigator/config",
            json={"config": cfg, "expected_revision": got["record"]["revision"]},
            headers=_headers("user-a"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["record"]["config"]["flow_sample_seconds"] == 90
        assert body["record"]["revision"] == 2

    async def test_put_config_with_stale_revision_is_409(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        await client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": 1}, headers=_headers("user-a"))
        resp = await client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": 1}, headers=_headers("user-a"))
        assert resp.status_code == 409
        assert "REVISION_CONFLICT" in resp.text

    async def test_put_config_with_invalid_payload_is_400(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        cfg["fusion"]["base_weight"] = 999  # breaks weights-sum-to-100
        resp = await client.put(
            "/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]},
            headers=_headers("user-a"),
        )
        assert resp.status_code == 400
        assert "INVALID_CONFIG" in resp.text

    async def test_gate_mode_blocked_until_calibrated(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        cfg["enabled"] = True
        cfg["operating_mode"] = "gate"
        resp = await client.put(
            "/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]},
            headers=_headers("user-a"),
        )
        assert resp.status_code == 423
        assert "GATE_NOT_CALIBRATED" in resp.text

    async def test_validate_dry_run_does_not_persist(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        cfg["fusion"]["base_weight"] = 999
        resp = await client.post("/api/v1/kite/navigator/config/validate", json=cfg, headers=_headers("user-a"))
        assert resp.status_code == 400
        after = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        assert after["record"]["revision"] == 1  # unaffected by the failed validate

    async def test_reset_restores_disabled_defaults(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        cfg["enabled"] = True
        await client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]}, headers=_headers("user-a"))
        resp = await client.post("/api/v1/kite/navigator/config/reset", headers=_headers("user-a"))
        assert resp.status_code == 200
        assert resp.json()["record"]["config"]["enabled"] is False

    async def test_users_are_isolated(self, client):
        got_a = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg_a = got_a["record"]["config"]
        cfg_a["flow_sample_seconds"] = 120
        await client.put("/api/v1/kite/navigator/config", json={"config": cfg_a, "expected_revision": got_a["record"]["revision"]}, headers=_headers("user-a"))

        got_b = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-b"))).json()
        assert got_b["record"]["config"]["flow_sample_seconds"] == 60  # untouched default


class TestStatusEndpoint:
    async def test_status_reports_disabled_by_default(self, client):
        resp = await client.get("/api/v1/kite/navigator/status", headers=_headers("user-a"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["health"] == "DISABLED"
        assert body["enabled"] is False


class TestSnapshotEndpoint:
    async def test_snapshot_is_503_when_disabled(self, client):
        resp = await client.get("/api/v1/kite/navigator/snapshot/NIFTY 50", headers=_headers("user-a"))
        assert resp.status_code == 503

    async def test_snapshot_is_503_when_no_evidence_cached_yet(self, client):
        got = (await client.get("/api/v1/kite/navigator/config", headers=_headers("user-a"))).json()
        cfg = got["record"]["config"]
        cfg["enabled"] = True
        await client.put("/api/v1/kite/navigator/config", json={"config": cfg, "expected_revision": got["record"]["revision"]}, headers=_headers("user-a"))
        resp = await client.get("/api/v1/kite/navigator/snapshot/NIFTY 50", headers=_headers("user-a"))
        assert resp.status_code == 503


class TestSignalsEndpoints:
    async def test_list_signals_empty_by_default(self, client):
        resp = await client.get("/api/v1/kite/navigator/signals", headers=_headers("user-a"))
        assert resp.status_code == 200
        assert resp.json()["decisions"] == []

    async def test_get_unknown_signal_is_404(self, client):
        resp = await client.get("/api/v1/kite/navigator/signals/does-not-exist", headers=_headers("user-a"))
        assert resp.status_code == 404

    async def test_series_endpoint_returns_empty_points_by_default(self, client):
        resp = await client.get("/api/v1/kite/navigator/series/NIFTY 50", headers=_headers("user-a"))
        assert resp.status_code == 200
        assert resp.json()["points"] == []

    def test_shared_engine_signals_include_navigator_rows_when_supertrend_disabled(self):
        from app.api.v1.endpoints import kite_engine as kite_endpoint

        uid = "user-a"
        kite_state.set_config(uid, EngineConfigModel(engine_enabled=False, scan_indices=["NIFTY 50"]))
        rec = config_store.get(uid, default_underlyings=["NIFTY 50"])
        cfg = rec.config.model_copy(update={"enabled": True, "signal_origination": "heads_up"})
        config_store.save(uid, cfg, expected_revision=rec.revision, default_underlyings=["NIFTY 50"])
        nav_runtime._snapshots[uid] = nav_runtime.NavigatorSnapshot(
            generated_ms=1_700_000_000_001,
            rows=[
                EngineSignalRow(
                    underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL",
                    alignment=AlignmentChip(fast=0, mid=0, slow=0),
                    direction="long", option_type="CE", legs=[],
                    spot=22000.0, stop_loss=21900.0, score=50.0,
                    timestamp_ms=1_700_000_000_000, is_active=True,
                    is_fresh=False, source="navigator",
                )
            ],
        )

        resp = kite_endpoint._signals_response(uid)

        assert [row.source for row in resp.rows] == ["navigator"]
        assert resp.generated_ms == 1_700_000_000_001


class TestCalibrationEndpoint:
    async def test_calibration_reports_not_ready_by_default(self, client):
        resp = await client.get("/api/v1/kite/navigator/calibration", headers=_headers("user-a"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["calibration_readiness"] == "not_ready"
        assert body["latest_report"] is None


class TestDefaultUserFallback:
    async def test_missing_header_uses_default_user(self, client):
        resp = await client.get("/api/v1/kite/navigator/config")
        assert resp.status_code == 200
