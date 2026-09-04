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
    assert body["defaults"]["orb_fresh_minutes"] == 5
    assert body["defaults"]["preferred_orb_distance_pct"] == 0.5
    assert body["defaults"]["max_orb_distance_pct"] == 1.0
    assert body["defaults"]["max_stop_distance_pct"] == 1.5
    assert body["decision_defaults"]["trade_score"] == 55.0
    assert body["decision_defaults"]["conviction_required"] == 5
    assert body["decision_defaults"]["repeat_volume_ratio"] == 0.5
    assert sum(body["decision_weights"].values()) == 100.0
    assert body["strategy"]["version"] == "1.3.0"
    assert body["live_scan_defaults"]["max_candidates"] == 250
    assert "Kite NFO" in body["live_universe"]
    assert "transparent bounded score" in body["tier_score"]
    assert "causal replay without live-quote leakage" in body["parity"]["evidence_backed"]
    assert (
        any(
            "ORION proprietary numeric strength-score weights" in item
            for item in body["strategy"]["unknown_and_omitted"]
        )
    )


def test_compare_endpoint_aggregates_multiple_sessions_without_private_fields():
    rows = [
        {
            "session_date": "2026-09-02",
            "symbol": "AAA",
            "direction": "UP",
            "tier": "strong",
            "rvol": 5.0,
            "signal_time": "09:15",
            "orb_break_time": "09:16",
            "combo": True,
        },
        {
            "session_date": "2026-09-03",
            "symbol": "BBB",
            "direction": "DOWN",
            "tier": "explosive",
            "rvol": 11.0,
            "signal_time": "09:15",
            "orb_break_time": "09:18",
            "combo": False,
        },
    ]
    response = client().post(
        "/api/v1/opening-volume-leaders/compare",
        json={"orion_rows": rows, "sterling_rows": rows},
    )

    assert response.status_code == 200
    assert response.json()["summary"]["session_count"] == 2
    assert response.json()["summary"]["exact_match"] is True


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

    async def fake_scan(uid, *, as_of, scan_config, signal_config):
        observed.update(
            uid=uid,
            as_of=as_of,
            scan_config=scan_config,
            signal_config=signal_config,
        )
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
            "as_of": "2026-09-03T09:24:00+05:30",
        },
    )

    assert response.status_code == 200
    assert observed["uid"] == "tenant-a"
    assert observed["as_of"].isoformat() == "2026-09-03T09:24:00+05:30"
    assert observed["scan_config"].symbols == ("RELIANCE",)
    assert observed["scan_config"].include_watch is True
    assert observed["scan_config"].include_weak is False
    assert observed["scan_config"].max_candidates == 250
    assert observed["signal_config"].baseline_sessions == 10
