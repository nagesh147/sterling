"""Phase-3 derivatives-build correctness tests — API surface.

Locks in the 8 endpoints + adapter additions:
  • /derivatives/candidates returns row-shaped data with the new fields
  • /derivatives/preview returns a full decision
  • /derivatives/execute requires a still-valid freeze_token
  • /derivatives/config GET/POST roundtrips per-strategy overrides
  • /derivatives/greeks-budget returns net Greeks + per-position breakdown
  • /derivatives/funding/{ul} proxies through to the adapter
  • /derivatives/book/{symbol} proxies through to the adapter
  • DeltaIndiaAdapter.get_funding_rate caches + falls back on error
  • DeltaIndiaAdapter.get_l2_book resolves product_id → symbol
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.derivatives import router as derivatives_router
from app.engines.derivatives.freeze_token import get_store
from app.engines.derivatives.profiles import DEFAULT_PROFILES
from app.engines.derivatives.schemas import (
    DecisionStatus, DerivativesCandidate, DerivativesDecision, MarketContext,
    SignalContext, StrategyDerivativesProfile,
)


@pytest.fixture(autouse=True)
def _reset():
    from app.engines.risk import cooldown
    from app.services import live_safety
    cooldown.clear()
    live_safety.reset_all_for_tests()
    get_store().clear()
    yield
    cooldown.clear()
    live_safety.reset_all_for_tests()
    get_store().clear()


@pytest.fixture
def app(monkeypatch):
    """Minimal FastAPI app with the derivatives router mounted and just
    enough state for the endpoints to find their dependencies."""
    app = FastAPI()
    app.include_router(derivatives_router, prefix="/api/v1")

    # Fake adapter
    ad = AsyncMock()
    ad.get_index_price.return_value = 50_000.0
    ad.get_product_id.return_value = 27
    ad.get_funding_rate.return_value = {
        "funding_rate_8h_pct": 0.0001,
        "fetched_ts_ms": int(time.time() * 1000),
        "next_funding_ts_ms": None,
        "source": "live",
    }
    ad.get_l2_book.return_value = {
        "bids": [[49_990, 1.0], [49_980, 2.0]],
        "asks": [[50_010, 1.5], [50_020, 3.0]],
        "ts_ms": int(time.time() * 1000),
    }
    ad.get_option_chain.return_value = []          # tests that need a chain inject their own
    app.state.adapter = ad

    # Fake CB / calibration / Greeks checker
    from app.engines.risk.circuit_breaker import DrawdownCircuitBreaker, CircuitBreakerConfig
    from app.engines.risk.greeks_budget import GreeksBudget, GreeksBudgetChecker
    cb = DrawdownCircuitBreaker(CircuitBreakerConfig(), portfolio_value=100_000.0)
    app.state.dd_circuit_breaker = cb
    app.state.greeks_budget_checker = GreeksBudgetChecker(GreeksBudget(), 100_000.0)

    cal = MagicMock()
    cal.win_rate.return_value = None
    app.state.calibration_service = cal

    # Force the instrument registry to know one underlying for the funding/book
    # tests. Was BTC with Delta perp/option identifiers; those fields are gone
    # and the registry is NSE-only now.
    from app.services.exchanges import instrument_registry as _reg
    nifty = MagicMock(underlying="NIFTY", has_options=True, min_dte=0)
    monkeypatch.setattr(_reg, "get_instrument",
                        lambda s: nifty if (s or "").upper() == "NIFTY" else None)

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ─── /config ───────────────────────────────────────────────────────────


class TestConfigEndpoints:
    def test_get_returns_default_profiles(self, client):
        r = client.get("/api/v1/derivatives/config")
        assert r.status_code == 200
        data = r.json()
        assert "directional" in data["profiles"]
        # Directional + edge feeds default enabled=True so their candidates SHOW
        # in the tables. The safety invariant is that AUTO-EXECUTION stays off
        # until the operator opts in per strategy.
        assert data["profiles"]["directional"]["enabled"] is True
        assert data["profiles"]["directional"]["auto_execute_futures"] is False
        assert data["profiles"]["directional"]["auto_execute_options"] is False

    def test_post_patches_profile(self, client):
        payload = StrategyDerivativesProfile(
            strategy="directional", enabled=True, leverage_cap=11.0,
        ).model_dump()
        r = client.post("/api/v1/derivatives/config", json={"profile": payload})
        assert r.status_code == 200
        body = r.json()
        assert body["profiles"]["directional"]["enabled"] is True
        assert body["profiles"]["directional"]["leverage_cap"] == 11.0
        # Re-GET should reflect the patch
        r2 = client.get("/api/v1/derivatives/config")
        assert r2.json()["profiles"]["directional"]["leverage_cap"] == 11.0


# ─── /funding ──────────────────────────────────────────────────────────


class TestFundingEndpoint:
    def test_reports_no_funding_leg_for_nse(self, client, app):
        """Funding is a perpetual-swap mechanism and NSE has none.

        This used to assert a live Delta funding rate for BTC. The endpoint now
        answers honestly instead of asking a Delta API for a fabricated
        "{SYM}USD" product and returning its 502.
        """
        r = client.get("/api/v1/derivatives/funding/NIFTY")
        assert r.status_code == 200
        body = r.json()
        assert body["funding_rate_8h_pct"] == 0.0
        assert body["source"] == "not_applicable"

    def test_unknown_underlying_503(self, client):
        r = client.get("/api/v1/derivatives/funding/UNOBTANIUM")
        assert r.status_code == 503


# ─── /book ─────────────────────────────────────────────────────────────


class TestBookEndpoint:
    def test_returns_l2(self, client):
        r = client.get("/api/v1/derivatives/book/BTCUSD?depth=2")
        assert r.status_code == 200
        body = r.json()
        assert len(body["bids"]) == 2
        assert body["asks"][0][0] == 50_010


# ─── /greeks-budget ────────────────────────────────────────────────────


class TestGreeksBudgetEndpoint:
    def test_empty_portfolio_returns_zeros(self, client):
        r = client.get("/api/v1/derivatives/greeks-budget")
        assert r.status_code == 200
        body = r.json()
        assert body["net_greeks"]["delta"] == 0.0
        assert body["positions"] == []
        assert "budget" in body


# ─── /preview ──────────────────────────────────────────────────────────


class TestPreviewEndpoint:
    def test_preview_returns_decision(self, client):
        r = client.get(
            "/api/v1/derivatives/preview",
            params={
                # Scalping-tier profiles default enabled=False (operator opts
                # in), so this exercises the PROFILE_OFF gate. (directional and
                # edge/* feeds default enabled=True for display.)
                "strategy": "conservative/price_action", "underlying": "NIFTY",
                "direction": "long", "entry": 50_000,
                "stop_loss": 49_000, "take_profit": 53_000,
                "atr": 1_000, "signal_score": 75,
            },
        )
        assert r.status_code == 200
        body = r.json()
        # Profile disabled by default → PROFILE_OFF
        assert body["status"] == "profile_off"

    def test_preview_with_enabled_profile_returns_decision(self, client):
        # Enable directional first
        enabled = DEFAULT_PROFILES["directional"].model_copy(update={"enabled": True})
        client.post("/api/v1/derivatives/config", json={"profile": enabled.model_dump()})
        r = client.get(
            "/api/v1/derivatives/preview",
            params={
                "strategy": "directional", "underlying": "NIFTY",
                "direction": "long", "entry": 50_000,
                "stop_loss": 49_000, "take_profit": 53_000,
                "atr": 1_000, "signal_score": 75,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["chosen"] is not None
        assert body["freeze_token"]
        assert body["freeze_token_ttl_ms"] == 120_000


# ─── /candidates ───────────────────────────────────────────────────────


class TestCandidatesEndpoint:
    def test_returns_empty_when_no_signals(self, client):
        r = client.get("/api/v1/derivatives/candidates")
        assert r.status_code == 200
        body = r.json()
        assert body["candidates"] == []


# ─── /execute ──────────────────────────────────────────────────────────


class TestExecuteEndpoint:
    def test_rejects_stale_token(self, client):
        r = client.post("/api/v1/derivatives/execute", json={
            "freeze_token": "nonexistent_token",
            "candidate_idx": 0,
        })
        assert r.status_code == 409
        detail = r.json()["detail"]
        assert detail["code"] == "stale_candidate"

    def test_rejects_out_of_range_idx(self, client):
        # Freeze a decision with no alternatives
        dec = DerivativesDecision(
            status=DecisionStatus.OK,
            chosen=DerivativesCandidate(
                rank=0, instrument_type="futures", underlying="NIFTY",
                entry_price=50_000, direction="long",
                contracts=1.0, leverage=5.0, notional_usd=50_000,
                stop_loss=49_000, take_profit=51_000, expected_r=2.0,
            ),
            alternatives=[],
            timestamp_ms=int(time.time() * 1000),
        )
        token, _ = get_store().freeze(dec)
        r = client.post("/api/v1/derivatives/execute", json={
            "freeze_token": token, "candidate_idx": 5,
        })
        assert r.status_code == 400


# ─── adapter direct ────────────────────────────────────────────────────

