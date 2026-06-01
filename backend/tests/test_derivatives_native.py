"""Phase 2a — native derivatives engine: config, engine, producer swap."""
from __future__ import annotations

import time
import pytest

from app.engines.derivatives_native.config import (
    ALPHA_SOURCES, DerivativesEngineConfig, EngineMode, RiskPosture,
)


class TestEngineConfig:
    def test_defaults(self):
        c = DerivativesEngineConfig()
        assert c.engine_mode == EngineMode.ROUTING_GATE
        assert c.active_alpha_sources == ["directional_futures"]
        assert c.risk_posture == RiskPosture.LONG_ONLY
        assert c.validation_method == 1

    def test_rejects_unknown_alpha_source(self):
        with pytest.raises(ValueError):
            DerivativesEngineConfig(active_alpha_sources=["directional_futures", "bogus"])

    def test_rejects_bad_validation_method(self):
        with pytest.raises(ValueError):
            DerivativesEngineConfig(validation_method=4)

    def test_alpha_sources_constant(self):
        assert ALPHA_SOURCES == {
            "directional_futures", "vrp_voltiming", "skew_put", "gex_pinning"}


from app.engines.derivatives_native.config import get_engine_config, set_engine_config


class _FakeState:
    pass


class _FakeApp:
    def __init__(self):
        self.state = _FakeState()


class TestEngineConfigAccessors:
    def test_get_seeds_default_when_absent(self, monkeypatch):
        import app.engines.derivatives_native.config as cfgmod
        monkeypatch.setattr(cfgmod, "get_config", lambda key, default="": "")
        app = _FakeApp()
        c = get_engine_config(app)
        assert c.engine_mode == EngineMode.ROUTING_GATE
        # cached on app.state
        assert app.state.derivatives_engine_config is c

    def test_set_persists_and_caches(self, monkeypatch):
        import app.engines.derivatives_native.config as cfgmod
        saved = {}
        monkeypatch.setattr(cfgmod, "set_config",
                            lambda key, value: saved.__setitem__(key, value))
        app = _FakeApp()
        cfg = DerivativesEngineConfig(engine_mode=EngineMode.NATIVE)
        out = set_engine_config(app, cfg)
        assert out.engine_mode == EngineMode.NATIVE
        assert app.state.derivatives_engine_config.engine_mode == EngineMode.NATIVE
        assert "derivatives_engine_config" in saved
        assert "native" in saved["derivatives_engine_config"]

    def test_get_loads_persisted(self, monkeypatch):
        import app.engines.derivatives_native.config as cfgmod
        raw = DerivativesEngineConfig(engine_mode=EngineMode.NATIVE).model_dump_json()
        monkeypatch.setattr(cfgmod, "get_config", lambda key, default="": raw)
        app = _FakeApp()
        c = get_engine_config(app)
        assert c.engine_mode == EngineMode.NATIVE


from app.engines.derivatives.freeze_token import get_store
from app.engines.derivatives.schemas import (
    DecisionStatus, MarketContext, SignalContext,
)
from app.engines.derivatives_native import engine as native_engine


@pytest.fixture(autouse=True)
def _reset_freeze():
    get_store().clear()
    yield
    get_store().clear()


def _signal(direction="long", entry=50000.0, atr=500.0) -> SignalContext:
    return SignalContext(
        strategy="edge/ma_crossover", underlying="BTC", direction=direction,
        entry=entry, stop_loss=entry - 2 * atr, take_profit=entry + 4 * atr,
        atr=atr, rr_target=2.0, signal_score=85.0, presized=True,
    )


def _market(spot=50000.0, ivr=90.0) -> MarketContext:
    # ivr=90 would trip the routing gate's ivr_pct_naked_max veto; native ignores it.
    return MarketContext(spot=spot, underlying="BTC", ivr_pct=ivr,
                         funding_8h_pct=0.0, portfolio_value=100_000.0)


class TestNativeFuturesLeg:
    def test_emits_futures_when_directional_active(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["directional_futures"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(), chain=None, config=cfg)
        assert dual.futures is not None
        assert dual.futures.status == DecisionStatus.OK
        assert dual.futures.chosen.instrument_type == "futures"
        assert dual.futures.freeze_token  # frozen so /execute works
        assert dual.status == DecisionStatus.OK

    def test_no_futures_when_source_inactive(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["skew_put"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(), chain=None, config=cfg)
        assert dual.futures is None


from app.schemas.market import OptionSummary


def _chain_btc(spot=50000.0) -> list[OptionSummary]:
    """Tradeable call+put chain around spot (14 DTE, tight spread). Time value
    decays with distance from spot so spreads have non-zero net premium."""
    out = []
    for strike in (46000, 47000, 48000, 49000, 50000, 51000, 52000, 53000, 54000):
        for opt_type in ("call", "put"):
            intrinsic = max(0.0, spot - strike) if opt_type == "call" else max(0.0, strike - spot)
            tv = max(50.0, 1200.0 - 0.30 * abs(strike - spot))
            mark = intrinsic + tv
            out.append(OptionSummary(
                instrument_name=f"{'C' if opt_type == 'call' else 'P'}-BTC-{strike}-140625",
                underlying="BTC", strike=float(strike), expiry_date="140625", dte=14,
                option_type=opt_type, bid=mark * 0.985, ask=mark * 1.015,
                mark_price=mark, mid_price=mark, mark_iv=55.0,
                delta=(0.55 if strike <= spot else 0.40) * (1 if opt_type == "call" else -1),
                gamma=0.0006, vega=20.0, theta=-15.0, rho=5.0,
                open_interest=400.0, volume_24h=200.0,
                last_updated_ms=int(time.time() * 1000), spread_pct=0.03))
    return out


class TestNativeOptionsLeg:
    def test_emits_long_premium_when_options_source_active(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["directional_futures", "vrp_voltiming"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options is not None
        assert dual.options.status == DecisionStatus.OK
        assert dual.options.chosen.instrument_type == "options"
        assert dual.options.freeze_token

    def test_overfilter_bypass_high_ivr_still_emits_futures(self):
        # ivr=90 > edge profile ivr_pct_naked_max(50): routing gate would veto
        # options→futures via instrument_chooser. Native emits futures directly.
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["directional_futures"])
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=90.0), chain=_chain_btc(), config=cfg)
        assert dual.futures.status == DecisionStatus.OK

    def test_defined_risk_builds_structure(self):
        # 2b: defined_risk now builds a multi-leg structure (no long_only fallback).
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE,
            active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options.chosen.structure is not None
        assert not any("long_only" in w for w in dual.warnings)


from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.derivatives import router as derivatives_router


@pytest.fixture
def engine_client(monkeypatch):
    """Fresh app with the derivatives router + an in-memory config store so the
    real DB is never touched (won't flip the live engine config)."""
    import app.engines.derivatives_native.config as cfgmod
    store: dict[str, str] = {}
    monkeypatch.setattr(cfgmod, "get_config", lambda key, default="": store.get(key, default))
    monkeypatch.setattr(cfgmod, "set_config", lambda key, value: store.__setitem__(key, value))
    api = FastAPI()
    api.include_router(derivatives_router, prefix="/api/v1")
    return TestClient(api)


from app.engines.derivatives.schemas import (
    DerivativesCandidate, DerivativesStructure, StructureLeg,
)


class TestStructureSchema:
    def test_structure_holds_legs_and_economics(self):
        legs = [
            StructureLeg(option_type="call", side="buy", strike=50000, premium=1200, ratio=1),
            StructureLeg(option_type="call", side="sell", strike=52000, premium=600, ratio=1),
        ]
        s = DerivativesStructure(
            structure_type="debit_vertical", underlying="BTC", direction="long",
            legs=legs, contracts=2.0, net_premium_usd=1200.0,
            max_loss_usd=1200.0, max_profit_usd=2800.0, breakevens=[50600.0])
        assert len(s.legs) == 2
        assert s.max_loss_usd == 1200.0
        assert "debit_vertical" in s.summary()

    def test_candidate_accepts_structure(self):
        s = DerivativesStructure(
            structure_type="iron_condor", underlying="BTC", direction="neutral", legs=[])
        cand = DerivativesCandidate(
            instrument_type="options", underlying="BTC", entry_price=50000,
            direction="neutral", contracts=1.0, structure=s)
        assert cand.structure is not None
        assert cand.structure.structure_type == "iron_condor"


class TestEngineConfigEndpoints:
    def test_get_and_post_engine_config(self, engine_client):
        r = engine_client.get("/api/v1/derivatives/config/engine")
        assert r.status_code == 200
        assert r.json()["engine_mode"] == "routing_gate"

        r = engine_client.post("/api/v1/derivatives/config/engine", json={
            "engine_mode": "native",
            "active_alpha_sources": ["directional_futures", "vrp_voltiming"],
            "risk_posture": "long_only",
            "validation_method": 1,
        })
        assert r.status_code == 200
        assert r.json()["engine_mode"] == "native"

        r = engine_client.get("/api/v1/derivatives/config/engine")
        assert r.json()["engine_mode"] == "native"


from app.engines.derivatives_native import structures as st


class TestStructureEconomics:
    def test_debit_call_spread_math(self):
        legs = [
            StructureLeg(option_type="call", side="buy", strike=50000, premium=1200),
            StructureLeg(option_type="call", side="sell", strike=52000, premium=600),
        ]
        net, max_loss, max_profit, bes = st.compute_economics(legs, contracts=1.0)
        assert round(net, 2) == 600.0          # debit paid = 1200 - 600
        assert round(max_loss, 2) == 600.0     # = net debit
        assert round(max_profit, 2) == 1400.0  # width 2000 - debit 600
        assert bes == [50600.0]                 # K1 + debit

    def test_credit_put_spread_math(self):
        legs = [
            StructureLeg(option_type="put", side="sell", strike=49000, premium=800),
            StructureLeg(option_type="put", side="buy", strike=47000, premium=300),
        ]
        net, max_loss, max_profit, bes = st.compute_economics(legs, contracts=1.0)
        assert round(net, 2) == -500.0         # net credit received
        assert round(max_profit, 2) == 500.0   # = credit
        assert round(max_loss, 2) == 1500.0    # width 2000 - credit 500
        assert bes == [48500.0]                 # K_short - credit

    def test_contracts_scale_linearly(self):
        legs = [
            StructureLeg(option_type="call", side="buy", strike=50000, premium=1200),
            StructureLeg(option_type="call", side="sell", strike=52000, premium=600),
        ]
        _, ml1, _, _ = st.compute_economics(legs, contracts=1.0)
        _, ml3, _, _ = st.compute_economics(legs, contracts=3.0)
        assert round(ml3, 2) == round(ml1 * 3, 2)


class TestStructureBuilders:
    def test_build_debit_vertical_long(self):
        s = st.build_debit_vertical(
            chain=_chain_btc(), spot=50000.0, direction="long",
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is not None
        assert s.structure_type == "debit_vertical"
        assert len(s.legs) == 2
        assert s.legs[0].side == "buy" and s.legs[1].side == "sell"
        assert s.legs[1].strike > s.legs[0].strike    # call spread: long lower, short higher
        assert 0 < s.max_loss_usd <= 0.02 * 100_000.0 + 1e-6

    def test_build_returns_none_when_strikes_missing(self):
        thin = [o for o in _chain_btc() if o.strike == 50000]
        s = st.build_debit_vertical(
            chain=thin, spot=50000.0, direction="long",
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is None

    def test_build_credit_vertical_long(self):
        s = st.build_credit_vertical(
            chain=_chain_btc(), spot=50000.0, direction="long",
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is not None and s.structure_type == "credit_vertical"
        assert s.legs[0].side == "sell" and s.legs[0].option_type == "put"
        assert s.net_premium_usd < 0      # credit received
        assert 0 < s.max_loss_usd <= 0.02 * 100_000.0 + 1e-6

    def test_build_iron_condor(self):
        s = st.build_iron_condor(
            chain=_chain_btc(), spot=50000.0,
            width_pct=0.04, nav_usd=100_000.0, max_loss_pct=0.02)
        assert s is not None and s.structure_type == "iron_condor"
        assert len(s.legs) == 4
        assert s.net_premium_usd < 0      # net credit
        assert s.max_loss_usd > 0

    def test_build_short_strangle_is_undefined_risk(self):
        s = st.build_short_strangle(
            chain=_chain_btc(), spot=50000.0,
            width_pct=0.04, nav_usd=100_000.0, premium_pct=0.02)
        assert s is not None and s.structure_type == "short_strangle"
        assert len(s.legs) == 2
        assert all(l.side == "sell" for l in s.legs)
        assert s.defined is False         # uncapped tail
        assert s.net_premium_usd < 0      # credit collected


class TestNativeDefinedRisk:
    def test_vrp_defined_risk_builds_condor(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options is not None and dual.options.status == DecisionStatus.OK
        cand = dual.options.chosen
        assert cand.structure is not None
        assert cand.structure.structure_type == "iron_condor"
        assert cand.structure.max_loss_usd > 0
        assert not any("long_only" in w for w in dual.warnings)

    def test_skew_defined_risk_builds_credit_vertical(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["skew_put"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert dual.options.chosen.structure.structure_type == "credit_vertical"

    def test_naked_low_regime_falls_back_to_defined_risk(self):
        # ivr=20 → not rich → don't sell cheap vol naked; fall back to defined_risk.
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.NAKED)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        assert any("naked" in w.lower() for w in dual.warnings)
        # fell back to a defined-risk structure (capped)
        assert dual.options.chosen.structure.defined is True

    def test_naked_rich_regime_builds_uncapped_strangle(self):
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.NAKED)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=85.0), chain=_chain_btc(), config=cfg)
        s = dual.options.chosen.structure
        assert s.structure_type == "short_strangle"
        assert s.defined is False
        assert any("uncapped" in w.lower() or "tail" in w.lower() for w in dual.warnings)


from app.engines.derivatives_native import regime as rg


class TestRegime:
    def test_cheap_when_iv_below_realized(self):
        r = rg.compute_regime(atm_iv=0.30, realized_vol=0.40, underlying="BTC", iv_history=[])
        assert round(r.vrp, 3) == 0.75
        assert r.label == "cheap"
        assert r.provisional is True   # no IV history

    def test_rich_when_iv_well_above_realized(self):
        r = rg.compute_regime(atm_iv=0.60, realized_vol=0.40, underlying="BTC", iv_history=[])
        assert r.label == "rich"

    def test_fair_band(self):
        r = rg.compute_regime(atm_iv=0.44, realized_vol=0.40, underlying="BTC", iv_history=[])
        assert r.label == "fair"

    def test_unknown_when_no_realized(self):
        r = rg.compute_regime(atm_iv=0.40, realized_vol=None, underlying="BTC", iv_history=[])
        assert r.label == "unknown" and r.vrp is None

    def test_iv_percentile_non_provisional_with_enough_history(self):
        hist = [0.30 + 0.001 * i for i in range(80)]   # 80 samples, 0.30..0.379
        r = rg.compute_regime(atm_iv=0.35, realized_vol=0.40, underlying="BTC", iv_history=hist)
        assert r.provisional is False
        assert r.iv_percentile is not None and 0 <= r.iv_percentile <= 100


class TestStructureRow:
    def test_row_carries_structure_summary(self):
        from app.api.v1.endpoints.derivatives import _row_from_decision
        cfg = DerivativesEngineConfig(
            engine_mode=EngineMode.NATIVE, active_alpha_sources=["vrp_voltiming"],
            risk_posture=RiskPosture.DEFINED_RISK)
        dual = native_engine.decide_both(
            signal=_signal(), market=_market(ivr=20.0), chain=_chain_btc(), config=cfg)
        row = _row_from_decision(
            signal_id="sig1", signal=_signal(), decision=dual.options)
        assert row.structure_summary is not None
        assert "iron_condor" in row.structure_summary
        assert row.structure_max_loss_usd is not None and row.structure_max_loss_usd > 0
