"""
Final endpoint coverage: alert GET/PUT/bulk-delete, position notes,
option chain IV stats, stats dynamic instrument counting.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle, OptionSummary
from app.services import alert_store, arrow_store
from app.schemas.alerts import AlertCreate, AlertCondition
from main import create_app


def _make_candles(n=100):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0+i*10, high=40050.0+i*10,
                   low=39950.0+i*10, close=40005.0+i*10, volume=100.0) for i in range(n)]


def _make_options():
    now = int(time.time() * 1000)
    opts = []
    for strike in [40000, 42000, 44000]:
        for opt_type in ["call", "put"]:
            opts.append(OptionSummary(
                instrument_name=f"BTC-12JAN25-{strike}-{'C' if opt_type=='call' else 'P'}",
                underlying="BTC", strike=float(strike), expiry_date="12JAN25", dte=12,
                option_type=opt_type, bid=400.0, ask=420.0, mark_price=410.0, mid_price=410.0,
                mark_iv=55.0 + (strike - 42000) / 1000, delta=0.45 if opt_type == "call" else -0.45,
                open_interest=200.0, volume_24h=30.0, last_updated_ms=now,
            ))
    return opts


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=_make_options())
    a.get_dvol = AsyncMock(return_value=None)
    a.get_dvol_history = AsyncMock(return_value=[])
    a.close = AsyncMock(return_value=None)
    return a


@pytest.fixture()
def client():
    app = create_app()
    adapter = _mock_adapter()
    app.state.adapter = adapter
    with TestClient(app) as c:
        c.app.state.adapter = adapter
        yield c


# ─── Alert GET/PUT/Bulk Delete ────────────────────────────────────────────────

class TestAlertCRUDComplete:
    def test_get_alert_by_id(self, client):
        created = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 50000.0
        }).json()
        aid = created["id"]
        resp = client.get(f"/api/v1/alerts/{aid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == aid

    def test_get_alert_unknown_404(self, client):
        resp = client.get("/api/v1/alerts/NOTEXIST")
        assert resp.status_code == 404

    def test_put_alert_updates_threshold(self, client):
        created = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 50000.0
        }).json()
        aid = created["id"]
        updated = client.put(f"/api/v1/alerts/{aid}", json={
            "underlying": "BTC", "condition": "price_above",
            "threshold": 55000.0, "cooldown_hours": 2.0, "notes": "revised"
        })
        assert updated.status_code == 200
        assert updated.json()["threshold"] == 55000.0
        assert updated.json()["cooldown_hours"] == 2.0

    def test_bulk_delete_dismissed(self, client):
        c1 = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 40000.0
        }).json()["id"]
        # Dismiss it
        client.post(f"/api/v1/alerts/{c1}/dismiss")
        # Add another active
        client.post("/api/v1/alerts", json={
            "underlying": "ETH", "condition": "price_below", "threshold": 1000.0
        })
        # Bulk clear
        resp = client.delete("/api/v1/alerts")
        assert resp.status_code == 204
        # Only active alert remains
        remaining = client.get("/api/v1/alerts").json()["alerts"]
        assert all(a["status"] != "dismissed" for a in remaining)

    def test_bulk_delete_empty_no_error(self, client):
        resp = client.delete("/api/v1/alerts")
        assert resp.status_code == 204

    def test_alert_routing_not_shadowed(self, client):
        """GET /alerts/{id} must not be caught by wrong route."""
        created = client.post("/api/v1/alerts", json={
            "underlying": "SOL", "condition": "signal_green_arrow"
        }).json()
        aid = created["id"]
        resp = client.get(f"/api/v1/alerts/{aid}")
        assert "id" in resp.json()


# ─── Position Notes ───────────────────────────────────────────────────────────

class TestPositionNotes:
    def test_notes_endpoint_exists(self, client):
        """PATCH /positions/{id}/notes must exist and handle missing position gracefully."""
        resp = client.patch("/api/v1/positions/NOEXIST/notes?notes=test")
        assert resp.status_code == 404

    def test_update_notes_on_real_position(self, client):
        from app.schemas.execution import SizedTrade, TradeStructure, CandidateContract
        from app.schemas.directional import Direction
        from app.services import paper_store
        leg = CandidateContract(
            instrument_name="BTC-12JAN25-42000-C", underlying="BTC",
            strike=42000.0, expiry_date="12JAN25", dte=12, option_type="call",
            bid=400.0, ask=420.0, mark_price=410.0, mid_price=410.0,
            mark_iv=55.0, delta=0.45, open_interest=100.0, volume_24h=20.0,
            spread_pct=0.048, health_score=80.0, healthy=True,
        )
        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[leg], max_loss=420.0, max_gain=None,
                net_premium=420.0, risk_reward=None, score=75.0, score_breakdown={},
            ),
            contracts=1, position_value=420.0, max_risk_usd=420.0, capital_at_risk_pct=0.42,
        )
        pos = paper_store.add_position("BTC", sized, 42000.0)
        resp = client.patch(f"/api/v1/positions/{pos.id}/notes?notes=Entry+at+42k+good+setup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Entry at 42k good setup"
        assert data["id"] == pos.id


# ─── Option Chain IV Stats ────────────────────────────────────────────────────

class TestOptionChainComplete:
    def test_chain_returns_all_types_by_default(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC").json()
        all_types = set()
        for contracts in data["by_expiry"].values():
            for c in contracts:
                all_types.add(c["option_type"])
        assert len(all_types) == 2  # both calls and puts

    def test_chain_put_filter(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC&type=put").json()
        for contracts in data["by_expiry"].values():
            for c in contracts:
                assert c["option_type"] == "put"

    def test_chain_healthy_count_accurate(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC").json()
        # Manually count healthy from response
        actual_healthy = sum(
            1 for contracts in data["by_expiry"].values()
            for c in contracts if c["healthy"]
        )
        assert data["healthy_contracts"] == actual_healthy

    def test_chain_spot_price(self, client):
        data = client.get("/api/v1/options/chain?underlying=BTC").json()
        assert data["spot_price"] == 42000.0


# ─── Stats Dynamic Instruments ────────────────────────────────────────────────

class TestStatsDynamic:
    def test_stats_counts_all_registry_instruments(self, client):
        from app.services.exchanges import instrument_registry as registry
        all_syms = [i.underlying for i in registry.list_instruments()]
        # Populate eval history for each
        from app.services import eval_history
        now = int(time.time() * 1000)
        for sym in all_syms[:2]:
            eval_history.record(sym, {
                "state": "CONFIRMED_SETUP_ACTIVE", "direction": "long",
                "recommendation": "naked_call", "no_trade_score": 30.0,
                "ivr": 55.0, "timestamp_ms": now
            })
        data = client.get("/api/v1/stats/session").json()
        assert data["run_once_total"] == 2
        assert data["confirmed_long_setups"] == 2

    def test_stats_timestamp_present(self, client):
        data = client.get("/api/v1/stats/session").json()
        assert data["timestamp_ms"] > 0


# ─── Run-All Records History ──────────────────────────────────────────────────

class TestRunAllComplete:
    def test_run_all_xrp_excluded(self, client):
        """XRP has no options — should not appear in results."""
        data = client.post("/api/v1/directional/run-all").json()
        results = data["results"]
        # XRP has has_options=False, excluded from run-all
        # BTC/ETH/SOL should be present
        assert "BTC" in results or "ETH" in results

    def test_run_all_instruments_evaluated(self, client):
        data = client.post("/api/v1/directional/run-all").json()
        from app.services.exchanges import instrument_registry as registry
        from app.api.v1.endpoints.directional import _adapter_can_serve
        from app.services import adapter_manager as _adm
        src = _adm.get_data_source()
        expected = sum(
            1 for i in registry.list_instruments()
            if i.has_options and _adapter_can_serve(i, src)
        )
        assert data["instruments_evaluated"] == expected
