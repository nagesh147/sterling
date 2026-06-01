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
