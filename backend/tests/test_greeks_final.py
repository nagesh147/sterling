"""
Final integration tests: paper portfolio Greeks, monitor-all P&L recording,
full pipeline (4H regime → 1H signal → setup → score → recommendation).
"""
import numpy as np
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from app.services import pnl_history, paper_store
from main import create_app

# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_candles(n=100, base=40000.0, trend=10.0):
    np.random.seed(42)
    return [Candle(
        timestamp_ms=1_700_000_000_000 + i * 3_600_000,
        open=base + i * trend, high=base + i * trend + 50,
        low=base + i * trend - 50, close=base + i * trend + 5, volume=100.0,
    ) for i in range(n)]


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


# ─── Portfolio Greeks ─────────────────────────────────────────────────────────

class TestPortfolioGreeks:
    def test_greeks_endpoint_exists(self, client):
        resp = client.get("/api/v1/positions/greeks")
        assert resp.status_code == 200

    def test_greeks_empty_portfolio(self, client):
        data = client.get("/api/v1/positions/greeks").json()
        assert data["total_delta"] == 0.0
        assert data["open_positions"] == 0
        assert data["net_directional_exposure"] == "neutral"

    def test_greeks_routing_not_shadowed(self, client):
        """Must not be caught by /{pos_id}."""
        resp = client.get("/api/v1/positions/greeks")
        assert "total_delta" in resp.json()

    def test_greeks_fields(self, client):
        data = client.get("/api/v1/positions/greeks").json()
        assert "total_delta" in data
        assert "net_directional_exposure" in data
        assert "open_positions" in data
        assert "timestamp_ms" in data

    def test_greeks_with_paper_position(self, client):
        from app.schemas.execution import SizedTrade, TradeStructure, CandidateContract
        from app.schemas.directional import Direction
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
            contracts=2, position_value=840.0, max_risk_usd=840.0, capital_at_risk_pct=0.84,
        )
        paper_store.add_position("BTC", sized, 42000.0)
        data = client.get("/api/v1/positions/greeks").json()
        assert data["open_positions"] == 1
        # delta = 0.45 * 2 contracts * long(+1) = 0.90
        assert abs(data["total_delta"] - 0.90) < 0.01
        assert data["net_directional_exposure"] == "bullish"


# ─── Monitor-all P&L recording ───────────────────────────────────────────────

class TestMonitorAllPnLRecord:
    def test_monitor_all_records_pnl_history(self, client):
        from app.schemas.execution import SizedTrade, TradeStructure, CandidateContract
        from app.schemas.directional import Direction
        leg = CandidateContract(
            instrument_name="ETH-12JAN25-2000-P", underlying="ETH",
            strike=2000.0, expiry_date="12JAN25", dte=10, option_type="put",
            bid=100.0, ask=120.0, mark_price=110.0, mid_price=110.0,
            mark_iv=60.0, delta=-0.40, open_interest=50.0, volume_24h=10.0,
            spread_pct=0.17, health_score=70.0, healthy=True,
        )
        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_put", direction=Direction.SHORT,
                legs=[leg], max_loss=120.0, max_gain=None,
                net_premium=120.0, risk_reward=None, score=65.0, score_breakdown={},
            ),
            contracts=1, position_value=120.0, max_risk_usd=120.0, capital_at_risk_pct=0.12,
        )
        pos = paper_store.add_position("ETH", sized, 2000.0)

        resp = client.post("/api/v1/positions/monitor-all")
        assert resp.status_code == 200

        snapshots = pnl_history.get_history(pos.id)
        assert len(snapshots) >= 1
        assert snapshots[-1].spot_price > 0


# ─── Full Pipeline Integration ────────────────────────────────────────────────

class TestFullPipeline:
    """End-to-end: candles → regime → signal → setup → run-once → recommendation."""

    def test_run_once_returns_valid_structure(self, client):
        resp = client.post("/api/v1/directional/run-once?underlying=BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert data["paper_mode"] is True
        assert "state" in data
        assert "direction" in data
        assert "recommendation" in data
        assert "timestamp_ms" in data

    def test_snapshot_all_fields(self, client):
        resp = client.get("/api/v1/directional/snapshot?underlying=ETH")
        assert resp.status_code == 200
        data = resp.json()
        required = ["underlying", "spot_price", "macro_regime", "signal_trend",
                    "all_green", "all_red", "green_arrow", "red_arrow",
                    "st_trends", "score_long", "score_short", "state",
                    "direction", "exec_mode", "exec_confidence", "timestamp_ms"]
        for f in required:
            assert f in data, f"Missing: {f}"

    def test_watchlist_all_instruments(self, client):
        resp = client.get("/api/v1/directional/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        underlyings = {item["underlying"] for item in data["items"]}
        assert {"BTC", "ETH", "SOL", "XRP"} <= underlyings

    def test_backtest_produces_bars(self, client):
        resp = client.post("/api/v1/backtest/run", json={
            "underlying": "BTC", "lookback_days": 7, "sample_every_n_bars": 6
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        s = data["stats"]
        total = s["bullish_regime_bars"] + s["bearish_regime_bars"] + s["neutral_regime_bars"]
        assert total == s["total_bars_evaluated"]

    def test_health_shows_all_fields(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert data["version"] == "0.4.0"
        assert data["paper_trading"] is True
        assert "positions" in data
        assert "exchange_adapter" in data

    def test_instruments_all_present(self, client):
        resp = client.get("/api/v1/instruments")
        assert resp.status_code == 200
        instruments = {i["underlying"] for i in resp.json()["instruments"]}
        assert {"BTC", "ETH", "SOL", "XRP"} <= instruments

    def test_regime_trend_returns_bars(self, client):
        resp = client.get("/api/v1/directional/regime-trend/BTC?n_bars=20")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 20
        if data["bars"]:
            bar = data["bars"][0]
            assert bar["regime"] in ("bullish", "bearish", "neutral")

    def test_exchange_delta_active_on_boot(self, client):
        resp = client.get("/api/v1/account/info")
        assert resp.json()["active"] is True
        assert resp.json()["exchange_name"] == "delta_india"

    def test_alert_lifecycle(self, client):
        # Create → Check → Triggered → Dismiss
        crt = client.post("/api/v1/alerts", json={
            "underlying": "BTC", "condition": "price_above", "threshold": 40000.0,
            "notes": "integration test",
        })
        assert crt.status_code == 200
        aid = crt.json()["id"]

        chk = client.post("/api/v1/alerts/check")
        assert chk.json()["newly_triggered"] >= 1

        dismissed = client.post(f"/api/v1/alerts/{aid}/dismiss")
        assert dismissed.json()["status"] == "dismissed"

    def test_paper_positions_full_lifecycle(self, client):
        # list → empty → analytics → greeks → export
        assert client.get("/api/v1/positions").json()["open_count"] == 0
        assert client.get("/api/v1/positions/analytics").json()["total_closed"] == 0
        assert client.get("/api/v1/positions/greeks").json()["open_positions"] == 0
        export = client.get("/api/v1/positions/export")
        assert export.status_code == 200
        assert "text/csv" in export.headers["content-type"]

    def test_config_info_complete(self, client):
        data = client.get("/api/v1/config/info").json()
        assert "BTC" in data["supported_underlyings"]
        assert "BTC" in data["underlyings_with_options"]
        assert "CachingAdapter" in data["adapter_stack"]

    def test_supported_exchanges_complete(self, client):
        data = client.get("/api/v1/exchanges/supported").json()
        names = {e["name"] for e in data["exchanges"]}
        assert {"delta_india", "zerodha", "deribit", "okx"} <= names
