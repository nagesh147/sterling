"""
Phase A tests — strategy upgrades.

Covers:
  A1: option_translation_engine delta-band wiring
  A2: trailing_stop adaptive trail_mult + tightening_offset
  A3: scoring uses composite health_score
  A4: scoring session bonus
  A5: scoring funding-window veto
  A6: dynamic_tp helper
"""
from __future__ import annotations
import time
import numpy as np
import pytest

from app.schemas.market import OptionSummary, Candle
from app.schemas.directional import (
    Direction, IVRBand, RegimeResult, MacroRegime, SignalResult,
    ExecTimingResult, ExecMode, PolicyResult,
)
from app.schemas.execution import CandidateContract, TradeStructure
from app.core.trading_mode import TrailMode
from app.engines.directional.option_translation_engine import (
    default_delta_band, get_healthy_candidates, translate_options,
)
from app.engines.directional.trailing_stop import (
    TrailingStopEngine, TrailState, _adaptive_base_mult, _atr_percentile,
)
from app.engines.directional import scoring
from app.engines.directional.dynamic_tp import dynamic_tp


# ─── shared fixtures ────────────────────────────────────────────────────────

def _opt(strike: float, dte: int, opt_type: str = "call",
         delta: float = 0.50, oi: float = 500, vol: float = 50,
         bid: float = 1.0, ask: float = 1.05, mark_iv: float = 0.7) -> OptionSummary:
    now_ms = int(time.time() * 1000)
    mid = (bid + ask) / 2
    return OptionSummary(
        instrument_name=f"BTC-{dte}-{int(strike)}-{opt_type[0].upper()}",
        underlying="BTC",
        strike=strike, expiry_date="2026-06-30", dte=dte,
        option_type=opt_type, bid=bid, ask=ask,
        mark_price=mid, mid_price=mid,
        mark_iv=mark_iv, delta=delta,
        open_interest=oi, volume_24h=vol,
        last_updated_ms=now_ms,
    )


def _instrument():
    from app.schemas.instruments import InstrumentMeta
    return InstrumentMeta(
        underlying="BTC", tick_size=0.5, strike_step=100.0,
        has_options=True, exchange="deribit", exchange_currency="BTC",
        perp_symbol="BTC-PERPETUAL", index_name="btc_usd", dvol_symbol="BTC_DVOL",
        min_dte=5, preferred_dte_min=10, preferred_dte_max=21,
    )


def _policy(band: IVRBand, ivr: float = 50.0):
    return PolicyResult(
        allowed_structures=["naked_call", "bull_call_spread"],
        ivr=ivr, ivr_band=band,
        preferred_dte_min=10, preferred_dte_max=21,
        naked_allowed=True, debit_preferred=False, avoid_long_premium=False,
    )


def _structure_with_health(health: float, structure_type: str = "naked_call") -> TradeStructure:
    leg = CandidateContract(
        instrument_name="BTC-X", underlying="BTC", strike=100000.0,
        expiry_date="2026-06-30", dte=14, option_type="call",
        bid=1.0, ask=1.05, mark_price=1.025, mid_price=1.025,
        mark_iv=0.7, delta=0.50, open_interest=500, volume_24h=50,
        spread_pct=0.05, health_score=health, healthy=True,
    )
    return TradeStructure(
        structure_type=structure_type, direction=Direction.LONG,
        legs=[leg], max_loss=1.05, max_gain=2.0, net_premium=1.05,
        risk_reward=1.9, score=0.0, score_breakdown={},
    )


def _futures_structure() -> TradeStructure:
    return TradeStructure(
        structure_type="futures", direction=Direction.LONG,
        legs=[], max_loss=1500.0, max_gain=3000.0, net_premium=0.0,
        risk_reward=2.0, score=0.0, score_breakdown={}, leverage=5,
        entry_price=100000.0,
    )


def _regime():
    return RegimeResult(
        macro_regime=MacroRegime.BULL_TREND, ema50=99000.0, close_4h=100000.0,
        score=18.0, atr_percentile=55.0, adx=25.0, ema21=99500.0, ema55=98500.0,
        atr_slope=0.0001,
    )


def _signal():
    return SignalResult(
        trend=1, all_green=True, all_red=False,
        green_arrow=False, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[99000.0, 98500.0, 98000.0],
        close_1h=100000.0, score_long=100.0, score_short=0.0,
        signal_strength="STRONG", signal_score=18.0, rsi=62.0,
        squeezed=False, ha_real_divergence_pct=0.05, vol_confirm=True,
    )


def _exec():
    return ExecTimingResult(mode=ExecMode.PULLBACK, confidence=0.8,
                            reason="pullback", exec_score=14.0)


# ─── A1 ──────────────────────────────────────────────────────────────────────

class TestA1DeltaBand:
    def test_band_widens_for_high_ivr(self):
        lo_low, hi_low = default_delta_band(IVRBand.LOW)
        lo_high, hi_high = default_delta_band(IVRBand.HIGH)
        # HIGH band starts lower (wings) than LOW band (long premium)
        assert lo_high < lo_low

    def test_band_filters_extreme_delta(self):
        inst = _instrument()
        pol = _policy(IVRBand.NORMAL)
        chain = [
            _opt(strike=100000, dte=14, delta=0.50),   # ATM keep
            _opt(strike=120000, dte=14, delta=0.05),   # deep OTM drop
            _opt(strike=80000,  dte=14, delta=0.95),   # deep ITM drop
        ]
        out = get_healthy_candidates(inst, pol, chain, spot_price=100000.0,
                                     option_type="call",
                                     target_delta_band=(0.18, 0.65))
        assert len(out) == 1
        assert out[0].strike == 100000

    def test_zero_delta_passes_through(self):
        """Adapters without greeks report delta=0.0 — must not be filtered."""
        inst = _instrument()
        pol = _policy(IVRBand.NORMAL)
        chain = [_opt(strike=100000, dte=14, delta=0.0)]
        out = get_healthy_candidates(inst, pol, chain, spot_price=100000.0,
                                     option_type="call",
                                     target_delta_band=(0.18, 0.65))
        assert len(out) == 1

    def test_translate_options_uses_default_band(self):
        inst = _instrument()
        pol = _policy(IVRBand.NORMAL)
        # delta=0.50 falls inside (0.18, 0.65)
        chain = [_opt(strike=100000, dte=14, delta=0.50, opt_type="call"),
                 _opt(strike=100000, dte=14, delta=-0.50, opt_type="put")]
        calls, puts = translate_options(inst, Direction.LONG, pol, chain, 100000.0)
        assert len(calls) >= 1
        assert len(puts) >= 1


# ─── A2 ──────────────────────────────────────────────────────────────────────

class TestA2AdaptiveTrail:
    def test_base_mult_scales_with_atr_pct(self):
        assert _adaptive_base_mult(0.0) == pytest.approx(1.5, abs=0.01)
        assert _adaptive_base_mult(50.0) == pytest.approx(2.5, abs=0.01)
        assert _adaptive_base_mult(100.0) == pytest.approx(3.5, abs=0.01)

    def test_atr_percentile_handles_short_array(self):
        assert _atr_percentile(np.array([])) == 50.0
        assert _atr_percentile(np.array([1.0, 2.0, 3.0])) == 50.0

    def test_atr_percentile_high_value(self):
        # Latest ATR is the max → percentile near 100
        arr = np.linspace(1.0, 10.0, 50)
        pct = _atr_percentile(arr)
        assert pct >= 95.0

    def test_trail_widens_in_high_vol(self):
        """High ATR percentile → wider trail (preserves more profit room)."""
        engine = TrailingStopEngine()
        # Uptrending candles with steady ATR
        candles = [
            Candle(timestamp_ms=i * 3600_000, open=100.0 + i,
                   high=101.0 + i, low=99.0 + i, close=100.5 + i, volume=10.0)
            for i in range(20)
        ]
        st = TrailState(
            mode=TrailMode.ATR, current_stop=99.0,
            highest_seen=119.5, lowest_seen=99.0,
            trail_mult=2.0, partial_25_pct=0.10, partial_50_pct=0.20,
        )
        from app.core.trading_mode import MODES
        cfg = MODES["swing"]
        out = engine.update(st, candles, st_value=99.0, direction="bullish",
                            entry_price=100.5, mode=cfg, initial_tp=120.0)
        # state.trail_mult is now the effective multiplier (1.5–3.5)
        assert 1.0 <= st.trail_mult <= 3.5

    def test_partial_50_increments_offset_not_mult(self):
        engine = TrailingStopEngine()
        candles = [
            Candle(timestamp_ms=i * 3600_000, open=100.0,
                   high=125.0, low=99.0, close=125.0, volume=10.0)
            for i in range(20)
        ]
        st = TrailState(
            mode=TrailMode.ATR, current_stop=99.0,
            highest_seen=125.0, lowest_seen=99.0,
            trail_mult=2.0, partial_25_pct=0.10, partial_50_pct=0.20,
            partial_25_done=True, breakeven_set=True,
        )
        from app.core.trading_mode import MODES
        cfg = MODES["swing"]
        out = engine.update(st, candles, st_value=99.0, direction="bullish",
                            entry_price=100.0, mode=cfg, initial_tp=130.0)
        # 25% gain at entry=100 close=125 → 50% partial threshold fires
        assert st.partial_50_done is True
        assert st.tightening_offset >= 0.5

    def test_state_json_roundtrip_back_compat(self):
        # Older snapshots without tightening_offset must still load
        s = '''{"mode":"atr","current_stop":99.0,"highest_seen":120.0,
                "lowest_seen":99.0,"partial_25_done":false,"partial_50_done":false,
                "breakeven_set":false,"trail_mult":2.0,
                "partial_25_pct":0.10,"partial_50_pct":0.20}'''
        st = TrailState.from_json(s)
        assert st.tightening_offset == 0.0


# ─── A3 ──────────────────────────────────────────────────────────────────────

class TestA3HealthScore:
    def test_high_health_scores_higher(self):
        bad = scoring._score_contract_health_v2(_structure_with_health(20.0))
        good = scoring._score_contract_health_v2(_structure_with_health(95.0))
        assert good > bad
        assert good <= 20.0
        assert bad >= 0.0

    def test_funding_penalty_still_applied(self):
        s = _structure_with_health(95.0)
        clean = scoring._score_contract_health_v2(s, funding_rate=0.0)
        bad   = scoring._score_contract_health_v2(s, funding_rate=0.01)  # 1% funding
        assert clean > bad

    def test_futures_gets_baseline(self):
        f = _futures_structure()
        v = scoring._score_contract_health_v2(f)
        assert v == 18.0


# ─── A4 ──────────────────────────────────────────────────────────────────────

class TestA4SessionBonus:
    def test_us_eu_overlap_max(self):
        assert scoring._score_session_bonus(15) == 3.0
        assert scoring._score_session_bonus(13) == 3.0
        assert scoring._score_session_bonus(16) == 3.0

    def test_us_extension(self):
        assert scoring._score_session_bonus(18) == 2.0

    def test_eu_morning(self):
        assert scoring._score_session_bonus(9) == 1.5

    def test_dead_zone_returns_zero(self):
        # Dead zone hours produce a hard veto upstream, but the bonus itself
        # is just 0 — the veto is a separate gate.
        assert scoring._score_session_bonus(4) == 0.0

    def test_bonus_uplifts_total_in_breakdown(self):
        s = _structure_with_health(60.0)  # mid health → mid score
        scored = scoring.score_structure(
            s, _regime(), _signal(), _exec(),
            _policy(IVRBand.NORMAL), bar_hour_utc=14, bar_minute_utc=20,
        )
        assert "session_bonus" in scored.score_breakdown
        assert scored.score_breakdown["session_bonus"] == 3.0


# ─── A5 ──────────────────────────────────────────────────────────────────────

class TestA5FundingWindow:
    def test_in_window_pre_boundary(self):
        assert scoring._in_funding_window(7, 50) is True   # before 08:00
        assert scoring._in_funding_window(15, 46) is True  # before 16:00
        assert scoring._in_funding_window(23, 59) is True  # before 00:00

    def test_in_window_post_boundary(self):
        assert scoring._in_funding_window(0, 5) is True
        assert scoring._in_funding_window(8, 14) is True
        assert scoring._in_funding_window(16, 0) is True

    def test_out_of_window(self):
        assert scoring._in_funding_window(10, 30) is False
        assert scoring._in_funding_window(14, 0) is False
        assert scoring._in_funding_window(8, 16) is False

    def test_funding_window_vetoes_score(self):
        s = _structure_with_health(80.0)
        scored = scoring.score_structure(
            s, _regime(), _signal(), _exec(),
            _policy(IVRBand.NORMAL), bar_hour_utc=8, bar_minute_utc=10,
        )
        assert scored.score == 0.0
        assert "funding window" in scored.score_breakdown.get("veto_reason", "")


# ─── A6 ──────────────────────────────────────────────────────────────────────

class TestA6DynamicTp:
    def test_long_picks_min_of_r_and_swing(self):
        highs = np.array([102.0, 103.0, 105.0, 104.0, 102.0])
        lows  = np.array([99.0, 100.0, 101.0, 100.0, 99.0])
        # Long entry 100, stop_dist 2, rr 2 → r_target = 104
        # swing_high 105, atr 1, atr_mult 1.5 → swing_target = 106.5
        # min(104, 106.5) = 104 → r_target wins
        tp, src = dynamic_tp("long", 100.0, 2.0, 2.0, highs, lows, atr=1.0)
        assert tp == 104.0
        assert src == "r_target"

    def test_long_picks_swing_when_closer(self):
        highs = np.array([100.5, 100.8, 101.0, 100.7, 100.6])
        lows  = np.array([99.0, 99.5, 99.8, 99.5, 99.0])
        # Long entry 100, stop_dist 2, rr 2 → r_target = 104
        # swing_high 101.0, atr 0.5, atr_mult 1.5 → swing_target = 101.75 (closer)
        tp, src = dynamic_tp("long", 100.0, 2.0, 2.0, highs, lows, atr=0.5)
        assert tp == 101.75
        assert src == "swing"

    def test_short_picks_max_of_r_and_swing(self):
        highs = np.array([101.0, 100.5, 100.0, 99.5, 99.0])
        lows  = np.array([95.0, 96.0, 97.0, 98.0, 99.0])
        # Short entry 100, stop_dist 2, rr 2 → r_target = 96
        # swing_low 95.0, atr 1.0, atr_mult 1.5 → swing_target = 93.5
        # max(96, 93.5) = 96 → r_target wins
        tp, src = dynamic_tp("short", 100.0, 2.0, 2.0, highs, lows, atr=1.0)
        assert tp == 96.0
        assert src == "r_target"

    def test_empty_arrays_falls_back_to_r_target(self):
        tp, src = dynamic_tp("long", 100.0, 2.0, 2.0,
                             np.array([]), np.array([]), atr=1.0)
        assert tp == 104.0
        assert src == "r_target"

    def test_zero_inputs_fallback(self):
        tp, src = dynamic_tp("long", 0.0, 2.0, 2.0,
                             np.array([1.0]), np.array([0.5]), atr=1.0)
        assert src == "fallback"
