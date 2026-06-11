"""Directional signal + regime engines emit REAL, honest signals — not the
fabricated `score=85` / `adx = 10 + int(close)%30` stubs they replaced."""
from __future__ import annotations

import math

from app.schemas.market import Candle
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.indicators import adx14, candles_to_df


def _c(i, px):
    return Candle(timestamp_ms=i * 3_600_000, open=px, high=px * 1.004,
                  low=px * 0.996, close=px, volume=100.0)


def _trend(n=120, start=100.0, step=0.01):
    """Steady uptrend (step>0) or downtrend (step<0)."""
    return [_c(i, start * (1 + step) ** i) for i in range(n)]


def _chop(n=120, start=100.0, amp=0.01):
    return [_c(i, start * (1 + amp * math.sin(i / 2.0))) for i in range(n)]


def test_adx_higher_in_trend_than_chop():
    a_trend = adx14(candles_to_df(_trend())).iloc[-1]
    a_chop = adx14(candles_to_df(_chop())).iloc[-1]
    assert a_trend > a_chop
    assert a_trend > 20  # a clean trend registers real strength


def test_signal_uptrend_is_long_and_not_hardcoded_85():
    r = compute_signal(_trend(step=0.012))
    assert r.trend == 1
    assert r.score_long > r.score_short
    assert r.score_long > 0
    assert r.signal_score != 85.0          # the fabrication is gone
    assert r.signal_strength in ("STRONG", "SIGNAL")


def test_signal_score_varies_with_conviction():
    # A stronger, cleaner trend should not score identically to a weak one.
    strong = compute_signal(_trend(step=0.02)).score_long
    weak = compute_signal(_chop(amp=0.004)).score_long
    assert strong != weak                   # honest = varying, not constant 85


def test_signal_empty_is_none():
    r = compute_signal([])
    assert r.signal_strength == "NONE"
    assert r.signal_score == 0.0
    assert r.trend == 0


def test_signal_downtrend_is_short():
    r = compute_signal(_trend(step=-0.012))
    assert r.trend == -1
    assert r.score_short > r.score_long


def test_regime_real_adx_and_direction():
    up = compute_regime(_trend(step=0.012))
    assert up.macro_regime.value in ("BULL_TREND", "bull_trending")
    assert up.adx > 0
    # the stub computed adx = 10 + int(close)%30; a real ADX won't equal that.
    close = float(_trend(step=0.012)[-1].close)
    assert abs(up.adx - (10.0 + (int(close) % 30))) > 1e-6
    down = compute_regime(_trend(step=-0.012))
    assert down.macro_regime.value in ("BEAR_TREND", "bear_trending")
    assert down.score < up.score


def test_regime_empty_is_idle():
    r = compute_regime([])
    assert r.macro_regime.value == "IDLE"
    assert r.score == 0.0


# ── Fix #1 (loosened arming) + #2 (WATCHING tier) for evaluate_setup ──────
from app.engines.directional.setup_engine import evaluate_setup
from app.schemas.directional import (
    RegimeResult, SignalResult, TradeState, Direction, MacroRegime,
)


def _reg(regime):
    return RegimeResult(macro_regime=regime, ema50=100.0, close_4h=100.0, score=50.0, adx=30.0)


def _sig(trend):
    return SignalResult(
        trend=trend, all_green=False, all_red=False, green_arrow=False, red_arrow=False,
        st_trends=[trend, trend, trend], st_values=[0.0, 0.0, 0.0], close_1h=100.0,
        score_long=70.0 if trend == 1 else 0.0, score_short=70.0 if trend == -1 else 0.0,
        signal_strength="SIGNAL" if trend else "NONE", signal_score=70.0 if trend else 0.0)


def test_bull_trend_1h_confirms_arms_continuation_long():
    s = evaluate_setup(_reg(MacroRegime.BULL_TREND), _sig(1))
    assert s.state == TradeState.ENTRY_ARMED_CONTINUATION and s.direction == Direction.LONG


def test_bull_trend_1h_neutral_arms_pullback_long():     # THE FIX: neutral 1h still arms
    s = evaluate_setup(_reg(MacroRegime.BULL_TREND), _sig(0))
    assert s.state == TradeState.ENTRY_ARMED_PULLBACK and s.direction == Direction.LONG


def test_bear_trend_1h_neutral_arms_pullback_short():     # matches live BTC (4h bear, 1h NONE)
    s = evaluate_setup(_reg(MacroRegime.BEAR_TREND), _sig(0))
    assert s.state == TradeState.ENTRY_ARMED_PULLBACK and s.direction == Direction.SHORT


def test_bear_trend_1h_confirms_arms_continuation_short():
    s = evaluate_setup(_reg(MacroRegime.BEAR_TREND), _sig(-1))
    assert s.state == TradeState.ENTRY_ARMED_CONTINUATION and s.direction == Direction.SHORT


def test_bull_trend_1h_contradicts_is_watching_with_bias():   # #2
    s = evaluate_setup(_reg(MacroRegime.BULL_TREND), _sig(-1))
    assert s.state == TradeState.WATCHING
    assert s.direction == Direction.LONG                       # 4h bias still shown
    assert s.state not in (TradeState.ENTRY_ARMED_PULLBACK, TradeState.ENTRY_ARMED_CONTINUATION)


def test_bear_trend_1h_contradicts_is_watching_with_bias():
    s = evaluate_setup(_reg(MacroRegime.BEAR_TREND), _sig(1))
    assert s.state == TradeState.WATCHING and s.direction == Direction.SHORT


def test_ranging_regime_is_idle():
    s = evaluate_setup(_reg(MacroRegime.RANGING), _sig(1))
    assert s.state == TradeState.IDLE and s.direction == Direction.NEUTRAL


def test_missing_inputs_idle():
    assert evaluate_setup(None, None).state == TradeState.IDLE
