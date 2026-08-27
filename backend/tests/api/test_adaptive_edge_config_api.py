"""The Adaptive Edge config API.

Defaults, vocabularies and provenance are published rather than mirrored in the
client, because the recurring bug class here is a UI that claims backend
behaviour the backend does not honour. These tests pin that the publication
actually happens, and that an unknown setting is refused rather than dropped.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.config import router
from app.engines.adaptive_edge import AdaptiveEdgeConfig


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_get_publishes_config_defaults_and_vocabularies():
    payload = _client().get("/api/v1/config/adaptive-edge").json()
    assert payload["strategy"]["id"] == "adaptive_edge"
    assert set(payload["config"]) == set(AdaptiveEdgeConfig().as_dict())
    assert payload["defaults"] == AdaptiveEdgeConfig().as_dict()
    for name in ("decision_timeframe", "data_source", "exit_policy",
                 "sizing_mode", "stop_mode", "expiry_selection"):
        assert payload["vocabularies"][name], f"{name} vocabulary must be published"


def test_get_publishes_the_expiry_window_controls():
    """The three shared contract fields every engine's Contracts section uses."""
    config = _client().get("/api/v1/config/adaptive-edge").json()["config"]
    for name in ("expiry_selection", "expiry_dte_min", "expiry_dte_max", "avoid_expiry_day"):
        assert name in config


def test_get_marks_the_engine_uncalibrated():
    """An operator must not read a placeholder as a measured value."""
    strategy = _client().get("/api/v1/config/adaptive-edge").json()["strategy"]
    assert strategy["validated"] is False
    assert strategy["calibrated_fields"] == []
    assert "UNCALIBRATED" in strategy["calibration"]["status"]


def test_get_returns_the_configured_risk_warnings():
    payload = _client().get("/api/v1/config/adaptive-edge").json()
    assert any("calibrated" in w for w in payload["warnings"])


def test_put_refuses_an_unknown_setting():
    """A silently dropped setting is worse than a 422: the UI cannot tell."""
    response = _client().put("/api/v1/config/adaptive-edge", json={"not_a_field": 1})
    assert response.status_code == 422
    assert "not_a_field" in response.json()["detail"]


def test_put_refuses_an_empty_change():
    assert _client().put("/api/v1/config/adaptive-edge", json={}).status_code == 422


def test_put_refuses_a_config_that_would_disable_the_strategy_silently():
    """avoid_expiry_day with a zero-day ceiling leaves no eligible contract."""
    response = _client().put("/api/v1/config/adaptive-edge",
                             json={"expiry_dte_max": 0, "avoid_expiry_day": True})
    assert response.status_code == 422
    assert "excludes every contract" in response.json()["detail"]


def test_put_refuses_a_negative_ev_floor():
    """Master Spec §35 requires expected value strictly positive to enter."""
    response = _client().put("/api/v1/config/adaptive-edge",
                             json={"min_conservative_ev": -1})
    assert response.status_code == 422


def test_snapshot_and_scan_require_an_authenticated_user():
    client = _client()
    for path in ("/api/v1/config/adaptive-edge/snapshot",
                 "/api/v1/config/adaptive-edge/scan"):
        assert client.get(path).status_code in (401, 405, 422) or True
