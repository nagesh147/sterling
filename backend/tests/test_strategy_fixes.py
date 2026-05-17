import pytest
from unittest.mock import MagicMock
from app.engines.directional.setup_engine import evaluate_setup
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
    signal = _signal(trend=1, all_green=True, green_count=3, score=14.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.EARLY_SETUP_ACTIVE


def test_idle_still_filtered():
    """IDLE regime is always filtered regardless of score."""
    regime = _regime(MacroRegime.IDLE)
    signal = _signal(trend=1, all_green=True, green_count=3, score=20.0)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.FILTERED


def test_trending_regime_unchanged():
    """Existing BULL_TREND confirmed path still works (no regression)."""
    regime = _regime(MacroRegime.BULL_TREND)
    signal = _signal(trend=1, all_green=True, green_count=3, score=15.0, arrow=True)
    result = evaluate_setup(regime, signal)
    assert result.state == TradeState.CONFIRMED_SETUP_ACTIVE
    assert result.direction == Direction.LONG
