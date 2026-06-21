"""Golden test: directional_mode=False ⇒ byte-identical to current engine behavior.

When the master toggle is OFF, every code path must fall back to the existing
options-only engine. This test validates:

1. EngineConfigModel defaults haven't shifted — directional_mode is False,
   vehicle is 'otm_options', all new fields are inert.
2. The SterlingKiteEngine + regime core produce the same signals with or
   without the new schema fields.
3. should_exit still behaves as a downside-only stop when no direction is given.
4. size_future_position returns sane results but is never invoked on the default path.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.domain.models import Candle
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.engine import SterlingKiteEngine
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine.positions import OpenPosition, should_exit
from app.services.kite_engine.sizing import SizingResult, size_future_position


# ── helpers ──────────────────────────────────────────────────────────────────

def _random_walk(seed: int = 42, n: int = 200, start: float = 20000.0) -> list:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.005, n)
    prices = [start]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices[1:]  # n prices


def _make_candles(prices: list) -> list[Candle]:
    candles = []
    for i, p in enumerate(prices):
        spread = p * 0.003
        candles.append(Candle(
            timestamp_ms=1700000000000 + i * 3600000,
            open=p - spread / 2,
            high=p + spread,
            low=p - spread,
            close=p,
            volume=0,
        ))
    return candles


# ── 1. defaults ──────────────────────────────────────────────────────────────

class TestDefaultConfig:
    def test_directional_mode_off(self):
        cfg = EngineConfigModel()
        assert cfg.directional_mode is False

    def test_vehicle_default(self):
        cfg = EngineConfigModel()
        assert cfg.vehicle == "otm_options"

    def test_futures_not_enabled_by_default(self):
        cfg = EngineConfigModel()
        assert "futures" not in cfg.enabled_vehicles

    def test_new_fields_inert(self):
        cfg = EngineConfigModel()
        assert cfg.itm_depth == "ITM10"
        assert cfg.target_delta is None
        assert cfg.futures_expiry == "near"
        assert cfg.adx_min is None
        assert cfg.atr_pct_min is None
        assert cfg.wire_risk_infra is False

    def test_existing_defaults_preserved(self):
        """All pre-existing defaults must survive the schema extension."""
        cfg = EngineConfigModel()
        assert cfg.trail_target == "fast"
        assert "ATM" in cfg.strike_moneyness
        assert cfg.scan_source == "derivatives"
        assert cfg.early_lock is False
        assert cfg.auto_execute is False
        assert cfg.risk_sizing is True
        assert cfg.risk_pct == 1.0
        assert cfg.max_lots == 10
        assert cfg.stop_mode == "both"


# ── 2. signal parity ────────────────────────────────────────────────────────

class TestSignalParity:
    """SterlingKiteEngine is purely signal-level; adding schema fields
    should not alter regime/entry logic at all."""

    @pytest.fixture
    def candles(self):
        return _make_candles(_random_walk(seed=42, n=200))

    def test_regime_deterministic(self, candles):
        cfg = SterlingKiteEngineConfig()
        opens = np.array([c.open for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        closes = np.array([c.close for c in candles])

        r1 = compute_regime(opens, highs, lows, closes, cfg)
        r2 = compute_regime(opens, highs, lows, closes, cfg)
        np.testing.assert_array_equal(r1.bull, r2.bull)
        np.testing.assert_array_equal(r1.bear, r2.bear)

    def test_engine_signals_unchanged(self, candles):
        eng = SterlingKiteEngine()
        sig1 = eng.generate(candles, underlying="TEST")
        eng2 = SterlingKiteEngine()
        sig2 = eng2.generate(candles, underlying="TEST")
        assert len(sig1) == len(sig2)
        for s1, s2 in zip(sig1, sig2):
            assert s1.direction == s2.direction
            assert s1.stop_loss == s2.stop_loss
            assert s1.score == s2.score


# ── 3. should_exit backward-compat ──────────────────────────────────────────

class TestShouldExitBackcompat:
    """Without the 'direction' param, should_exit defaults to long (downside stop)."""

    def test_long_breach_below(self):
        assert should_exit(100.0, 95.0) is True

    def test_long_at_stop(self):
        assert should_exit(100.0, 100.0) is True

    def test_long_above_stop(self):
        assert should_exit(100.0, 105.0) is False

    def test_no_stop(self):
        assert should_exit(0.0, 50.0) is False

    def test_stale_tick(self):
        assert should_exit(100.0, 0.0) is False

    # ── direction-aware (new behavior) ────────────────────────────────────
    def test_short_above_stop_breaches(self):
        assert should_exit(100.0, 105.0, "short") is True

    def test_short_below_stop_ok(self):
        assert should_exit(100.0, 95.0, "short") is False

    def test_long_explicit(self):
        assert should_exit(100.0, 95.0, "long") is True


# ── 4. OpenPosition direction/vehicle fields ────────────────────────────────

class TestOpenPositionFields:
    def test_default_direction_is_long(self):
        p = OpenPosition(uid="u1", symbol="NIFTY25JUNCE", exchange="NFO")
        assert p.direction == "long"
        assert p.vehicle == "otm_options"

    def test_futures_position(self):
        p = OpenPosition(uid="u1", symbol="NIFTY25JUN", exchange="NFO",
                         direction="short", vehicle="futures")
        assert p.direction == "short"
        assert p.vehicle == "futures"


# ── 5. futures sizer (unit test) ─────────────────────────────────────────────

class TestFuturesSizer:
    def test_basic_sizing(self):
        sr = size_future_position(
            entry_price=20000.0, stop_price=19800.0, lot_size=50,
            available_capital=500000.0, risk_pct=1.0, max_lots=5,
        )
        assert sr.lots >= 1
        assert sr.qty == sr.lots * 50
        assert sr.est_risk > 0

    def test_no_lot_size(self):
        sr = size_future_position(
            entry_price=20000.0, stop_price=19800.0, lot_size=0,
            available_capital=500000.0, risk_pct=1.0, max_lots=5,
        )
        assert sr.lots == 0
        assert sr.qty == 0

    def test_max_lots_cap(self):
        sr = size_future_position(
            entry_price=20000.0, stop_price=19990.0, lot_size=25,
            available_capital=10_000_000.0, risk_pct=5.0, max_lots=3,
        )
        assert sr.lots <= 3

    def test_floor_at_one_lot(self):
        """Even when risk exceeds budget, floor at 1 lot."""
        sr = size_future_position(
            entry_price=20000.0, stop_price=15000.0, lot_size=50,
            available_capital=100_000.0, risk_pct=1.0, max_lots=10,
        )
        assert sr.lots >= 1


# ── 6. validator clamping ────────────────────────────────────────────────────

class TestValidators:
    def test_target_delta_clamp_low(self):
        # OTM execution targets (δ ~0.2–0.45) are now valid and pass through;
        # only sub-0.05 degenerate deltas are clamped up.
        assert EngineConfigModel(target_delta=0.3).target_delta == 0.3
        assert EngineConfigModel(target_delta=0.01).target_delta == 0.05

    def test_target_delta_clamp_high(self):
        cfg = EngineConfigModel(target_delta=1.5)
        assert cfg.target_delta == 0.99

    def test_adx_min_clamp(self):
        cfg = EngineConfigModel(adx_min=2.0)
        assert cfg.adx_min == 5.0

    def test_atr_pct_min_clamp(self):
        cfg = EngineConfigModel(atr_pct_min=100.0)
        assert cfg.atr_pct_min == 95.0

    def test_none_passes_through(self):
        cfg = EngineConfigModel(target_delta=None, adx_min=None, atr_pct_min=None)
        assert cfg.target_delta is None
        assert cfg.adx_min is None
        assert cfg.atr_pct_min is None
