"""Replay endpoint contract: honest fills by default, refusals surfaced."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.nifty_orb_options import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _bar(minute, low, high, close, *, open_=None, spread=0.0, volume=1_000_000, oi=50_000):
    return {
        "timestamp": f"2026-01-28T09:{minute:02d}:00",
        "symbol": "NIFTY26JAN25000CE",
        "option_type": "CE",
        "strike": 25000,
        "expiry": "2026-01-29",
        "open": close if open_ is None else open_,
        "high": high,
        "low": low,
        "close": close,
        "bid": close - spread / 2,
        "ask": close + spread / 2,
        "volume": volume,
        "open_interest": oi,
        "lot_size": 75,
    }


BARS = [_bar(30, 100, 102, 101), _bar(35, 100, 102, 100, open_=100), _bar(40, 105, 112, 110)]


def test_replay_reports_option_level_pnl_with_a_next_bar_fill():
    response = client().post(
        "/api/v1/nifty-orb-options/replay",
        json={"bars": BARS, "trades": [{"entry_index": 0, "risk_points": 3, "target_r": 1, "lots": 2}]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["option_pnl"] is True
    assert payload["entry_delay_bars"] == 1
    assert payload["rejections"] == []
    trade = payload["trades"][0]
    assert trade["entry_time"].endswith("09:35:00")      # the bar after the signal
    assert trade["entry_price"] == 100.0
    assert trade["quantity"] == 150
    assert trade["exit_reason"] == "target"


def test_replay_surfaces_a_refused_signal_instead_of_dropping_it():
    illiquid = [BARS[0], _bar(35, 100, 102, 100, open_=100, volume=50), BARS[2]]
    response = client().post(
        "/api/v1/nifty-orb-options/replay",
        json={
            "bars": illiquid,
            "trades": [{"entry_index": 0, "risk_points": 3}],
            "admission": {"min_volume": 1000},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["trades"] == []
    assert payload["rejections"] == [{"entry_index": 0, "reason": "volume below admission floor"}]
    assert payload["metrics"]["trades"] == 0


def test_replay_applies_statutory_charges_when_requested():
    body = {"bars": BARS, "trades": [{"entry_index": 0, "risk_points": 3, "target_r": 1}]}
    free = client().post("/api/v1/nifty-orb-options/replay", json=body).json()
    costed = client().post(
        "/api/v1/nifty-orb-options/replay",
        json={**body, "statutory_costs": {"brokerage": 20, "slippage_per_share": 0}},
    ).json()
    assert free["metrics"]["total_costs"] == 0
    assert costed["metrics"]["total_costs"] > 0
    assert costed["metrics"]["net_pnl"] < free["metrics"]["net_pnl"]
    assert costed["metrics"]["gross_pnl"] == free["metrics"]["gross_pnl"]


def test_replay_rejects_an_empty_bar_series():
    response = client().post("/api/v1/nifty-orb-options/replay", json={"bars": [], "trades": []})
    assert response.status_code == 422
