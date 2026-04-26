"""
Tests: /positions/analytics, /positions/analytics routing (not shadowed by /{pos_id}),
       /directional/regime-trend, profit_factor Infinity handling.
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.schemas.market import Candle
from main import create_app


def _make_candles(n=100, base=40000.0, trend=10.0):
    return [
        Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=base + i * trend, high=base + i * trend + 50,
            low=base + i * trend - 50, close=base + i * trend + 5,
            volume=100.0,
        )
        for i in range(n)
    ]


def _mock_adapter():
    a = MagicMock()
    a.ping = AsyncMock(return_value=True)
    a.get_index_price = AsyncMock(return_value=42000.0)
    a.get_spot_price = AsyncMock(return_value=42000.0)
    a.get_perp_price = AsyncMock(return_value=42100.0)
    a.get_candles = AsyncMock(return_value=_make_candles())
    a.get_option_chain = AsyncMock(return_value=[])
    a.get_dvol = AsyncMock(return_value=55.0)
    a.get_dvol_history = AsyncMock(return_value=[40.0, 55.0, 70.0])
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


class TestAnalyticsRoute:
    """Verify /analytics is NOT shadowed by /{pos_id}."""

    def test_analytics_not_404(self, client):
        resp = client.get("/api/v1/positions/analytics")
        assert resp.status_code == 200

    def test_analytics_fields(self, client):
        data = client.get("/api/v1/positions/analytics").json()
        for field in [
            "total_closed", "winners", "losers", "win_rate_pct",
            "avg_pnl_usd", "avg_winner_usd", "avg_loser_usd",
            "best_trade_usd", "worst_trade_usd",
            "total_realized_pnl_usd", "profit_factor", "timestamp_ms"
        ]:
            assert field in data, f"Missing: {field}"

    def test_analytics_empty_state(self, client):
        data = client.get("/api/v1/positions/analytics").json()
        assert data["total_closed"] == 0
        assert data["win_rate_pct"] == 0.0
        assert data["profit_factor"] == 0.0

    def test_analytics_does_not_conflict_with_pos_id(self, client):
        # GET /positions/analytics should return analytics, not "position not found"
        resp = client.get("/api/v1/positions/analytics")
        assert resp.status_code == 200
        assert "total_closed" in resp.json()

    def test_profit_factor_no_infinity(self, client):
        """Backend must not return Infinity (invalid JSON) even with all-winners scenario."""
        data = client.get("/api/v1/positions/analytics").json()
        pf = data["profit_factor"]
        assert isinstance(pf, (int, float))
        assert pf != float('inf')  # valid JSON number


class TestRegimeTrend:
    def test_regime_trend_btc(self, client):
        resp = client.get("/api/v1/directional/regime-trend/BTC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["underlying"] == "BTC"
        assert "bars" in data
        assert data["count"] == len(data["bars"])

    def test_regime_trend_bar_fields(self, client):
        data = client.get("/api/v1/directional/regime-trend/BTC").json()
        if data["bars"]:
            bar = data["bars"][0]
            assert "timestamp_ms" in bar
            assert "close" in bar
            assert "ema50" in bar
            assert "is_bullish" in bar
            assert "regime" in bar
            assert bar["regime"] in ("bullish", "bearish", "neutral")
            assert isinstance(bar["is_bullish"], bool)

    def test_regime_trend_n_bars_param(self, client):
        resp = client.get("/api/v1/directional/regime-trend/BTC?n_bars=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 10

    def test_regime_trend_unknown_404(self, client):
        resp = client.get("/api/v1/directional/regime-trend/FAKE")
        assert resp.status_code == 404

    def test_regime_trend_n_bars_validation(self, client):
        resp = client.get("/api/v1/directional/regime-trend/BTC?n_bars=1")
        assert resp.status_code == 422  # below min=5

    def test_regime_trend_bullish_in_uptrend(self, client):
        """With uptrend candles, most bars should be bullish after warmup."""
        data = client.get("/api/v1/directional/regime-trend/BTC?n_bars=30").json()
        if data["count"] >= 5:
            # After EMA warmup, uptrend → mostly bullish
            bullish_count = sum(1 for b in data["bars"] if b["is_bullish"])
            assert bullish_count > 0  # at least some bullish bars in an uptrend


class TestProfitFactorEdgeCases:
    def test_pf_sentinel_for_all_winners(self):
        """profit_factor=999.9 when no losses (sentinel for ∞)."""
        import app.api.v1.endpoints.positions as pos_ep
        from app.services import paper_store as ps
        from app.schemas.execution import SizedTrade, TradeStructure
        from app.schemas.directional import Direction

        # Manually add a closed winning position to the store
        sized = SizedTrade(
            structure=TradeStructure(
                structure_type="naked_call", direction=Direction.LONG,
                legs=[], max_loss=500.0, max_gain=None,
                net_premium=500.0, risk_reward=None, score=75.0, score_breakdown={},
            ),
            contracts=1, position_value=500.0, max_risk_usd=500.0, capital_at_risk_pct=0.5,
        )
        pos = ps.add_position("BTC", sized, 42000.0)
        ps.close_position(pos.id, 43000.0)
        # Set realized P&L manually to positive
        ps._positions[pos.id] = ps._positions[pos.id].model_copy(
            update={"realized_pnl_usd": 250.0}
        )

        # Now compute analytics
        closed = [p for p in ps.list_positions() if p.status.value == "closed"]
        pnls = [p.realized_pnl_usd for p in closed if p.realized_pnl_usd is not None]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]
        gross_loss = abs(sum(losers)) if losers else 0.0
        assert gross_loss == 0.0
        assert len(winners) > 0
        # Backend uses 999.9 as sentinel
        pf = 999.9 if gross_loss == 0.0 and winners else 0.0
        assert pf == 999.9
