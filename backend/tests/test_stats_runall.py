"""
Tests: session stats, run-all, alert cooldown rearm.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from app.services import alert_store, arrow_store
from app.schemas.alerts import AlertCreate, AlertCondition, AlertStatus
from main import create_app


def _make_candles(n=100, trend=10.0):
    return [Candle(timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                   open=40000.0+i*trend, high=40050.0+i*trend,
                   low=39950.0+i*trend, close=40005.0+i*trend, volume=100.0) for i in range(n)]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
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


# ─── Session Stats ────────────────────────────────────────────────────────────

class TestSessionStats:
    def test_stats_empty(self, client):
        resp = client.get("/api/v1/stats/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["green_arrows"] == 0
        assert data["red_arrows"] == 0
        assert data["total_arrows"] == 0
        assert data["alerts_active"] == 0
        assert data["paper_positions_open"] == 0

    def test_stats_fields(self, client):
        data = client.get("/api/v1/stats/session").json()
        for f in ["green_arrows", "red_arrows", "total_arrows",
                  "alerts_active", "alerts_triggered", "alerts_dismissed",
                  "run_once_total", "confirmed_long_setups", "confirmed_short_setups",
                  "paper_positions_open", "paper_positions_closed",
                  "underlyings_with_arrows", "timestamp_ms"]:
            assert f in data, f"Missing: {f}"

    def test_stats_counts_arrows(self, client):
        now = int(time.time() * 1000)
        arrow_store.record("BTC", "green", 42000.0, "long", "IDLE", now, "test")
        arrow_store.record("ETH", "red", 3000.0, "short", "IDLE", now, "test")
        data = client.get("/api/v1/stats/session").json()
        assert data["green_arrows"] == 1
        assert data["red_arrows"] == 1
        assert data["total_arrows"] == 2

    def test_stats_counts_alerts(self, client):
        client.post("/api/v1/alerts", json={"underlying": "BTC", "condition": "price_above", "threshold": 40000.0})
        data = client.get("/api/v1/stats/session").json()
        assert data["alerts_active"] == 1

    def test_stats_after_run_once(self, client):
        client.post("/api/v1/directional/run-once?underlying=BTC")
        data = client.get("/api/v1/stats/session").json()
        assert data["run_once_total"] >= 1

    def test_underlyings_with_arrows(self, client):
        now = int(time.time() * 1000)
        arrow_store.record("SOL", "green", 100.0, "long", "IDLE", now, "test")
        data = client.get("/api/v1/stats/session").json()
        assert "SOL" in data["underlyings_with_arrows"]


# ─── Run-All ──────────────────────────────────────────────────────────────────

class TestRunAll:
    def test_run_all_returns_all_instruments(self, client):
        resp = client.post("/api/v1/directional/run-all")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "instruments_evaluated" in data
        assert data["instruments_evaluated"] >= 3  # BTC, ETH, SOL

    def test_run_all_results_keyed_by_underlying(self, client):
        data = client.post("/api/v1/directional/run-all").json()
        results = data["results"]
        assert "BTC" in results or "ETH" in results

    def test_run_all_each_has_state(self, client):
        data = client.post("/api/v1/directional/run-all").json()
        for underlying, result in data["results"].items():
            if "error" not in result:
                assert "state" in result
                assert "recommendation" in result

    def test_run_all_records_eval_history(self, client):
        client.post("/api/v1/directional/run-all")
        from app.services import eval_history
        btc_hist = eval_history.get_history("BTC")
        assert len(btc_hist) >= 1

    def test_run_all_timestamp(self, client):
        data = client.post("/api/v1/directional/run-all").json()
        assert data["timestamp_ms"] > 0


# ─── Alert Cooldown ───────────────────────────────────────────────────────────

class TestAlertCooldown:
    def test_cooldown_field_in_create(self, client):
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC",
            "condition": "price_above",
            "threshold": 40000.0,
            "cooldown_hours": 4.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cooldown_hours"] == 4.0

    def test_zero_cooldown_stays_triggered(self):
        """Alert with cooldown_hours=0 stays TRIGGERED after firing."""
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.PRICE_ABOVE, threshold=40000.0,
            cooldown_hours=0.0
        ))
        alert_store.fire_alert(alert.id, trigger_value=42000.0)
        rearmed = alert_store.rearm_if_cooldown_elapsed(alert.id)
        assert not rearmed
        assert alert_store.get_alert(alert.id).status == AlertStatus.TRIGGERED

    def test_cooldown_not_elapsed_stays_triggered(self):
        """Alert with cooldown > 0 stays TRIGGERED if cooldown hasn't elapsed."""
        alert = alert_store.add_alert(AlertCreate(
            underlying="ETH", condition=AlertCondition.PRICE_ABOVE, threshold=3000.0,
            cooldown_hours=24.0  # 24 hours — won't elapse in test
        ))
        alert_store.fire_alert(alert.id, trigger_value=3500.0)
        rearmed = alert_store.rearm_if_cooldown_elapsed(alert.id)
        assert not rearmed  # 24h hasn't passed
        assert alert_store.get_alert(alert.id).status == AlertStatus.TRIGGERED

    def test_cooldown_elapsed_rearmed(self):
        """Simulate cooldown elapsed → alert rearms to ACTIVE."""
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.PRICE_ABOVE, threshold=40000.0,
            cooldown_hours=0.001  # ~3.6 seconds
        ))
        # Fire it with a past trigger time (cooldown already elapsed)
        past_ms = int(time.time() * 1000) - 10_000  # 10 seconds ago
        # Manually set triggered_at_ms in the past
        fired = alert_store.fire_alert(alert.id, trigger_value=42000.0)
        # Patch triggered_at_ms to be in the past
        alert_store._alerts[alert.id] = fired.model_copy(update={"triggered_at_ms": past_ms})
        rearmed = alert_store.rearm_if_cooldown_elapsed(alert.id)
        assert rearmed
        assert alert_store.get_alert(alert.id).status == AlertStatus.ACTIVE

    def test_fire_count_increments(self):
        """fire_count tracks how many times alert has fired."""
        alert = alert_store.add_alert(AlertCreate(
            underlying="BTC", condition=AlertCondition.SIGNAL_GREEN_ARROW, cooldown_hours=0.0
        ))
        assert alert.fire_count == 0
        alert_store.fire_alert(alert.id)
        assert alert_store.get_alert(alert.id).fire_count == 1

    def test_check_rearms_before_evaluating(self, client):
        """POST /alerts/check rearms expired cooldowns before evaluating."""
        resp = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 40000.0,
            "cooldown_hours": 0.001,
        })
        aid = resp.json()["id"]
        # Manually trigger + set old trigger time
        from app.services import alert_store as ast
        ast.fire_alert(aid)
        old_ts = int(time.time() * 1000) - 20_000
        ast._alerts[aid] = ast._alerts[aid].model_copy(update={"triggered_at_ms": old_ts})
        assert ast.get_alert(aid).status == AlertStatus.TRIGGERED

        # Check should rearm + re-trigger since price 42000 > 40000
        resp2 = client.post("/api/v1/alerts/check")
        assert resp2.json()["newly_triggered"] >= 1
