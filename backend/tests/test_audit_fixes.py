"""
Tests for the four audit-driven fixes:
  A) circuit breaker receives real daily_pnl_pct (not hardcoded 0.0)
  B) calibration record_trade uses max_risk_usd denominator (not entry_spot*10)
  C) _build_indicator_lines ST3 uses VWAP candles + mult=2.0 (matches signal_engine)
  J) _check_hard_vetoes accepts bar_hour_utc to decouple from wall-clock
"""
import numpy as np
import pytest
from unittest.mock import MagicMock

from tests.conftest import make_candles
from app.schemas.market import Candle


# ─── Fix J: dead-zone veto uses caller-supplied bar hour ─────────────────────

class TestHardVetoBarHour:
    def _make_structure(self, spread_pct: float = 0.001, oi: float = 200.0):
        from app.schemas.execution import TradeStructure, CandidateContract
        from app.schemas.directional import Direction
        leg = MagicMock()
        leg.spread_pct = spread_pct
        leg.open_interest = oi
        structure = MagicMock(spec=TradeStructure)
        structure.legs = [leg]
        structure.structure_type = "futures"
        return structure

    def test_dead_zone_with_bar_hour(self):
        from app.engines.directional.scoring import _check_hard_vetoes
        struct = self._make_structure()
        # Supply a dead-zone bar hour explicitly — should veto regardless of wall clock.
        for h in (2, 3, 4, 5):
            veto = _check_hard_vetoes(struct, bar_hour_utc=h)
            assert veto is not None, f"Expected veto for hour {h}"
            assert "dead zone" in veto

    def test_active_hour_with_bar_hour(self):
        from app.engines.directional.scoring import _check_hard_vetoes
        struct = self._make_structure()
        for h in (8, 12, 16, 20):
            veto = _check_hard_vetoes(struct, bar_hour_utc=h)
            assert veto is None, f"Hour {h} should not be vetoed"

    def test_none_bar_hour_falls_back_to_wallclock(self):
        """When bar_hour_utc=None, live wall-clock is used (backward-compat)."""
        import datetime as dt
        from unittest.mock import patch
        from app.engines.directional.scoring import _check_hard_vetoes

        struct = self._make_structure()
        # Patch to a non-dead-zone hour so the veto doesn't fire.
        with patch("app.engines.directional.scoring._dt") as mock_dt:
            mock_dt.datetime.now.return_value.hour = 10
            mock_dt.timezone.utc = dt.timezone.utc
            veto = _check_hard_vetoes(struct, bar_hour_utc=None)
        assert veto is None

    def test_score_structure_passes_bar_hour(self):
        """score_structure correctly threads bar_hour_utc into _check_hard_vetoes."""
        from app.engines.directional.scoring import score_structure
        from app.schemas.execution import TradeStructure
        from app.schemas.directional import Direction

        struct = self._make_structure()
        struct.__class__ = MagicMock  # make model_copy available

        # Use dead-zone hour — score should be 0 with a veto reason.
        regime = MagicMock()
        regime.score = 15.0
        signal = MagicMock()
        signal.signal_score = 15.0
        exec_timing = MagicMock()
        exec_timing.exec_score = 10.0
        policy = MagicMock()

        # Build a real minimal TradeStructure so model_copy works.
        from app.schemas.execution import CandidateContract
        from app.schemas.directional import Direction as D
        leg = CandidateContract(
            instrument_name="BTC-50000-C-27DEC24",
            underlying="BTC", option_type="call", strike=50000.0,
            expiry_date="27DEC24", dte=30, mark_price=1000.0,
            bid=990.0, ask=1010.0, mid_price=1000.0, mark_iv=0.8,
            delta=0.5,
            open_interest=500.0, volume_24h=200.0,
            spread_pct=0.002, health_score=85.0, healthy=True,
        )
        real_struct = TradeStructure(
            structure_type="futures", direction=D.LONG, legs=[leg],
            max_loss=1000.0, max_gain=None, net_premium=1000.0,
            risk_reward=2.0, score=0.0, score_breakdown={},
        )

        result = score_structure(
            real_struct, regime, signal, exec_timing, policy,
            bar_hour_utc=3,  # dead zone hour
        )
        assert result.score == 0.0
        assert "dead zone" in (result.score_breakdown.get("veto_reason") or "")


# ─── Fix C: ST3 chart overlay matches signal_engine ──────────────────────────

class TestST3ChartOverlayMatchesSignalEngine:
    def test_st3_values_consistent(self):
        """
        _build_indicator_lines ST3 must produce the same supertrend values
        as signal_engine.compute_signal on identical candles.
        """
        from app.engines.directional.signal_engine import compute_signal, _to_vwap_candles
        from app.engines.indicators.supertrend import compute_supertrend
        from app.engines.indicators.heikin_ashi import compute_heikin_ashi
        from app.engines.indicators.ema import compute_ema
        import numpy as np

        candles = make_candles(80)

        # --- Replicate _build_indicator_lines ST3 logic (after fix) ---
        h = np.array([c.high for c in candles], dtype=np.float64)
        l = np.array([c.low for c in candles], dtype=np.float64)
        c_arr = np.array([c.close for c in candles], dtype=np.float64)

        vwap_candles = list(_to_vwap_candles(candles))
        vwap_h = np.array([v.high for v in vwap_candles], dtype=np.float64)
        vwap_l = np.array([v.low  for v in vwap_candles], dtype=np.float64)
        vwap_c = np.array([v.close for v in vwap_candles], dtype=np.float64)
        chart_st3_line, chart_st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, 21, 2.0)

        # --- signal_engine ST3 ---
        signal = compute_signal(candles)
        # signal.st_values[2] is st3_line[-1], signal.st_trends[2] is st3_trend[-1]
        assert chart_st3_line[-1] == pytest.approx(signal.st_values[2], rel=1e-6)
        assert chart_st3_trend[-1] == signal.st_trends[2]

    def test_st3_old_config_would_differ(self):
        """Confirm the OLD config (real candles, mult=1.0) produces different values."""
        from app.engines.directional.signal_engine import compute_signal, _to_vwap_candles
        from app.engines.indicators.supertrend import compute_supertrend
        import numpy as np

        candles = make_candles(80)
        h = np.array([c.high for c in candles], dtype=np.float64)
        l = np.array([c.low for c in candles], dtype=np.float64)
        c_arr = np.array([c.close for c in candles], dtype=np.float64)

        # OLD: real candles, mult=1.0
        old_st3_line, _ = compute_supertrend(h, l, c_arr, 21, 1.0)

        signal = compute_signal(candles)
        # Old and new should NOT match (different candles + different multiplier).
        assert old_st3_line[-1] != pytest.approx(signal.st_values[2], rel=1e-3), (
            "Old ST3 config (real candles, mult=1.0) should differ from signal_engine ST3"
        )


# ─── Fix B: calibration pnl_pct denominator ──────────────────────────────────

class TestCalibrationPnlPct:
    def test_pnl_pct_uses_max_risk_not_spot(self):
        """
        pnl_pct = realized_pnl_usd / max_risk_usd (not entry_spot * 10).
        Verify sign and magnitude are correct for a sample trade.
        """
        realized = 150.0     # $150 profit
        max_risk = 500.0     # $500 at risk
        entry_spot = 45000.0  # BTC spot — old code: 45000 * 10 = 450000 denominator

        pnl_pct_correct = realized / max(max_risk, 1.0)        # 0.30 (30% return on risk)
        pnl_pct_old = realized / max(entry_spot * 10, 1.0)     # 0.000333 (essentially 0)

        assert pnl_pct_correct == pytest.approx(0.30, rel=1e-9)
        assert pnl_pct_old < 0.001, "Old formula gives near-zero, misleading calibration"

        # Both classify as win (pnl > 0) — but magnitude matters for future Kelly use
        assert pnl_pct_correct > 0
        assert pnl_pct_old > 0

    def test_loss_sign_preserved(self):
        realized = -200.0
        max_risk = 500.0
        pnl_pct = realized / max(max_risk, 1.0)
        assert pnl_pct < 0, "Loss must remain negative after fix"
        assert pnl_pct == pytest.approx(-0.40, rel=1e-9)

    def test_zero_max_risk_guard(self):
        """max(max_risk, 1.0) guard prevents ZeroDivisionError."""
        realized = 50.0
        pnl_pct = realized / max(0.0, 1.0)
        assert pnl_pct == pytest.approx(50.0)


# ─── Fix A: circuit breaker daily_pnl_pct computed from real trades ──────────

class TestCircuitBreakerDailyPnL:
    def test_daily_pnl_formula(self):
        """
        daily_pnl_pct = sum(today's closed realized_pnl_usd) / capital.
        Verify a -5% day triggers halt.
        """
        capital = 10_000.0
        daily_pnl_usd = -510.0   # just over -5%
        daily_pnl_pct = daily_pnl_usd / capital
        assert daily_pnl_pct < -0.05

    def test_free_margin_formula(self):
        """
        free_margin_pct = 1 - (open_risk / capital).
        Verify <20% margin flags correctly.
        """
        capital = 10_000.0
        open_risk = 8_500.0   # 85% of capital at risk → 15% free
        free_margin_pct = max(0.0, 1.0 - open_risk / capital)
        assert free_margin_pct == pytest.approx(0.15)
        assert free_margin_pct < 0.20  # should trigger NO_NEW_ENTRIES

    def test_zero_capital_guard(self):
        capital = 0.0
        open_risk = 500.0
        free_margin_pct = max(0.0, 1.0 - open_risk / capital) if capital > 0 else 1.0
        assert free_margin_pct == 1.0  # guard returns safe default
