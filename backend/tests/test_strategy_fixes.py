import pytest
from unittest.mock import MagicMock
from app.engines.directional.setup_engine import evaluate_setup, _HIGH_SCORE_CONFIRM
from app.schemas.directional import (
    RegimeResult, SignalResult, MacroRegime, TradeState, Direction,
)

def _regime(macro):
    r = MagicMock(spec=RegimeResult)
    r.macro_regime = macro
    r.score = 0.0
    return r

def _signal(trend, all_green=False, all_red=False, green_count=3, red_count=0, score=0.0, arrow=False):
    s = MagicMock(spec=SignalResult)
    s.trend = trend
    s.all_green = all_green
    s.all_red = all_red
    s.st_trends = ([1]*green_count + [-1]*red_count + [0]*(3-green_count-red_count))[:3]
    s.signal_score = score
    s.green_arrow = arrow and trend == 1
    s.red_arrow   = arrow and trend == -1
    return s


def test_ranging_high_score_all_green_confirms_long():
    """RANGING + all 3 STs green + score >= 16 -> CONFIRMED_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=True, green_count=3, score=16.5)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.LONG


def test_ranging_high_score_all_red_confirms_short():
    """RANGING + all 3 STs red + score >= 16 -> CONFIRMED_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=-1, all_red=True, red_count=3, score=17.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.SHORT


def test_ranging_low_score_stays_early():
    """RANGING + all STs green but score < 16 -> still EARLY_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=True, green_count=3, score=12.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_ranging_partial_st_stays_early():
    """RANGING + only 2/3 STs green -> EARLY regardless of score."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=False, green_count=2, score=18.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_volatile_high_score_all_green_confirms():
    """VOLATILE + all STs green + score >= 16 -> CONFIRMED_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.VOLATILE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=16.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE


def test_volatile_low_score_stays_early():
    """VOLATILE + low score -> EARLY_SETUP_ACTIVE."""
    regime = _regime(MacroRegime.VOLATILE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=_HIGH_SCORE_CONFIRM - 1.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_idle_filtered_below_strict_threshold():
    """IDLE is filtered unless signal_score reaches the strict 17/20 opt-in.

    The IDLE veto was tightened to allow only near-max-confluence entries
    (>=17/20 with all STs aligned). At score 16 IDLE is still vetoed; at
    score 17+ it can confirm — that path is exercised by a separate test.
    """
    regime = _regime(MacroRegime.IDLE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=16.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.FILTERED


def test_idle_confirms_at_strict_threshold():
    """IDLE confirms when score >= 17 AND all STs aligned (strict opt-in)."""
    regime = _regime(MacroRegime.IDLE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=17.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.LONG


def test_trending_regime_unchanged():
    """Existing BULL_TREND confirmed path still works (no regression)."""
    regime = _regime(MacroRegime.BULL_TREND)
    signal = _signal(trend=1, all_green=True, green_count=3, score=15.0, arrow=True)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.LONG


def test_ranging_score_exactly_at_threshold_confirms():
    """score == _HIGH_SCORE_CONFIRM exactly (on-boundary) must confirm."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=True, green_count=3, score=_HIGH_SCORE_CONFIRM)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE


def test_ranging_score_just_below_threshold_stays_early():
    """score == _HIGH_SCORE_CONFIRM - 0.01 (just below) must stay EARLY."""
    regime = _regime(MacroRegime.RANGING)
    signal = _signal(trend=1, all_green=True, green_count=3, score=_HIGH_SCORE_CONFIRM - 0.01)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_neutral_regime_high_score_confirms():
    """NEUTRAL is in _RANGING_REGIMES — same promotion must apply."""
    regime = _regime(MacroRegime.NEUTRAL)
    signal = _signal(trend=1, all_green=True, green_count=3, score=17.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE


# ── Fix 2: score_min filter + signal_score in bar results ────────────────────
from app.engines.backtest.backtest_engine import simulate_capital_curve, run_backtest
from app.schemas.backtest import BacktestBarResult

def _bar(score=15.0, fwd12=2.0, state='CONFIRMED_SETUP_ACTIVE', direction='long'):
    return BacktestBarResult(
        timestamp_ms=1_700_000_000_000,
        close_1h=30000.0, close_4h=30000.0,
        macro_regime='BULL_TREND', ema50=29000.0,
        signal_trend=1, all_green=True, all_red=False,
        green_arrow=True, red_arrow=False,
        st_trends=[1, 1, 1], st_values=[29900.0, 29800.0, 29700.0],
        state=state, direction=direction,
        fwd_return_12h=fwd12,
        signal_score=score,
    )


def test_signal_score_field_on_bar_result():
    """BacktestBarResult must accept signal_score field."""
    bar = _bar(score=14.5)
    assert bar.signal_score == 14.5


def test_simulate_score_min_skips_low_score():
    """score_min=12 must skip bars with signal_score < 12."""
    # Need a sentinel bar at the end to close the last open trade (hold_bars=1)
    bars = [
        _bar(score=8.0,  fwd12=5.0),   # skipped — score too low
        _bar(score=14.0, fwd12=3.0),   # taken
        _bar(score=0.0,  fwd12=1.0, state='IDLE'),  # sentinel: closes previous, no new entry
    ]
    sim_no_filter = simulate_capital_curve(bars, capital=10_000, score_min=0.0, hold_bars=1)
    sim_filtered  = simulate_capital_curve(bars, capital=10_000, score_min=12.0, hold_bars=1)
    assert len(sim_no_filter['trades']) == 2
    assert len(sim_filtered['trades']) == 1


def test_simulate_score_min_zero_takes_all():
    """score_min=0 (default) takes all CONFIRMED bars regardless of score."""
    bars = [
        _bar(score=0.0, fwd12=2.0),
        _bar(score=1.0, fwd12=-1.0),
        _bar(score=0.0, fwd12=1.0, state='IDLE'),  # sentinel to close last trade
    ]
    sim = simulate_capital_curve(bars, capital=10_000, score_min=0.0, hold_bars=1)
    assert len(sim['trades']) == 2


def test_simulate_score_min_default_backward_compat():
    """Calling simulate_capital_curve without score_min still works."""
    bars = [
        _bar(score=5.0, fwd12=2.0),
        _bar(score=0.0, fwd12=1.0, state='IDLE'),  # sentinel to close last trade
    ]
    sim = simulate_capital_curve(bars, capital=10_000, hold_bars=1)
    assert len(sim['trades']) == 1


def test_run_backtest_populates_signal_score():
    """run_backtest bars must have signal_score populated."""
    from tests.conftest import make_candles
    c4h = make_candles(100, base=30000.0, trend=80.0)
    c1h = make_candles(400, base=30000.0, trend=20.0)
    res = run_backtest("BTC", c4h, c1h, lookback_days=30, sample_every_n_bars=4)
    assert len(res.bars) > 0
    scores = [b.signal_score for b in res.bars if b.signal_score is not None]
    assert len(scores) == len(res.bars)   # every bar has a score
    assert all(0.0 <= s <= 20.0 for s in scores)
