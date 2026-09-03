from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.opening_volume_leaders import router

IST = timezone(timedelta(hours=5, minutes=30))


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _row(session: date, at: time, volume: float, *, close: float = 101.0) -> dict:
    return {
        "timestamp": datetime.combine(session, at, tzinfo=IST).isoformat(),
        "open": 100.0,
        "high": max(102.0, close),
        "low": 99.0,
        "close": close,
        "volume": volume,
    }


def _payload() -> dict:
    return {
        "symbol": "TEST",
        "as_of": datetime(2026, 9, 3, 9, 17, tzinfo=IST).isoformat(),
        "average_turnover_inr": 25_000_000,
        "config": {"baseline_sessions": 2},
        "bars": [
            _row(date(2026, 9, 1), time(9, 15), 100),
            _row(date(2026, 9, 2), time(9, 15), 100),
            _row(date(2026, 9, 3), time(9, 15), 500, close=101.8),
            _row(date(2026, 9, 3), time(9, 16), 200, close=103.0),
        ],
    }


def test_contract_publishes_defaults_and_discloses_non_parity_fields():
    response = client().get("/api/v1/opening-volume-leaders/contract")
    assert response.status_code == 200
    body = response.json()
    assert body["defaults"]["baseline_sessions"] == 10
    assert body["defaults"]["spurt_rvol"] == 3.0
    assert body["defaults"]["strong_rvol"] == 5.0
    assert body["defaults"]["explosive_rvol"] == 10.0
    assert "not implemented" in body["tier_score"]
    assert (
        "proprietary numeric strength-score weights"
        in body["strategy"]["unknown_and_omitted"]
    )


def test_supplied_bar_evaluation_returns_the_causal_signal_contract():
    response = client().post("/api/v1/opening-volume-leaders/evaluate", json=_payload())
    assert response.status_code == 200
    signal = response.json()["signal"]
    assert signal["symbol"] == "TEST"
    assert signal["tier"] == "strong"
    assert signal["rvol"] == 5.0
    assert signal["signal_time"].startswith("2026-09-03T09:15:00")
    assert signal["orb_break_time"].startswith("2026-09-03T09:16:00")
    assert signal["signal_key"] == "opening-volume:2026-09-03:TEST:UP"
    assert "score" not in signal


def test_evaluation_rejects_non_monotonic_tier_thresholds():
    payload = _payload()
    payload["config"] = {"strong_rvol": 3.0}
    response = client().post("/api/v1/opening-volume-leaders/evaluate", json=payload)
    assert response.status_code == 422
    assert "watch < spurt < strong < explosive" in response.json()["detail"]


def test_evaluation_rejects_an_empty_bar_set_before_engine_work():
    payload = _payload()
    payload["bars"] = []
    response = client().post("/api/v1/opening-volume-leaders/evaluate", json=payload)
    assert response.status_code == 422


def test_live_scan_passes_only_validated_advisory_configuration(monkeypatch):
    observed = {}

    async def fake_scan(uid, *, scan_config, signal_config):
        observed.update(uid=uid, scan_config=scan_config, signal_config=signal_config)
        return {"leader_count": 0, "leaders": [], "failures": []}

    monkeypatch.setattr(
        "app.services.opening_volume_leaders.scan_kite_leaders",
        fake_scan,
    )
    response = client().post(
        "/api/v1/opening-volume-leaders/scan",
        headers={"X-User-Id": "tenant-a"},
        json={
            "scan_all_stocks": False,
            "symbols": ["RELIANCE"],
            "include_watch": True,
        },
    )

    assert response.status_code == 200
    assert observed["uid"] == "tenant-a"
    assert observed["scan_config"].symbols == ("RELIANCE",)
    assert observed["scan_config"].include_watch is True
    assert observed["signal_config"].baseline_sessions == 10
