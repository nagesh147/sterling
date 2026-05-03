import json
import pytest
import numpy as np
from app.schemas.market import Candle
from app.core.trading_mode import TrailMode, MODES
from app.engines.directional.trailing_stop import (
    TrailState, TrailingStopEngine, PartialExitSignal, TrailUpdate,
)


def _candles(n=30, base=30000.0, trend=10.0):
    np.random.seed(42)
    candles = []
    price = base
    for i in range(n):
        price += trend
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 60000,
            open=price - 10, high=price + 15, low=price - 15, close=price,
            volume=100.0,
        ))
    return candles


def _make_state(mode=TrailMode.ATR, stop=29500.0, high=30000.0, low=29000.0):
    return TrailState(
        mode=mode, current_stop=stop,
        highest_seen=high, lowest_seen=low,
        trail_mult=2.0,
    )


engine = TrailingStopEngine()
mode = MODES["swing"]


def test_atr_trail_only_moves_up_for_long():
    candles = _candles(30, base=30000.0, trend=50.0)
    state = _make_state(TrailMode.ATR, stop=29000.0, high=30000.0)
    update1 = engine.update(state, candles, st_value=29000.0, direction="bullish",
                            entry_price=30000.0, mode=mode)
    prev = update1.new_stop
    # Price keeps rising — stop should not decrease
    candles2 = _candles(30, base=31000.0, trend=50.0)
    update2 = engine.update(state, candles2, st_value=30000.0, direction="bullish",
                            entry_price=30000.0, mode=mode)
    assert update2.new_stop >= prev


def test_atr_trail_only_moves_down_for_short():
    candles = _candles(30, base=30000.0, trend=-50.0)
    state = _make_state(TrailMode.ATR, stop=31000.0, high=31000.0, low=30000.0)
    update1 = engine.update(state, candles, st_value=31000.0, direction="bearish",
                            entry_price=31000.0, mode=mode)
    prev = update1.new_stop
    candles2 = _candles(30, base=29000.0, trend=-50.0)
    update2 = engine.update(state, candles2, st_value=30000.0, direction="bearish",
                            entry_price=31000.0, mode=mode)
    assert update2.new_stop <= prev


def test_supertrend_trail_follows_st_value():
    candles = _candles(30)
    state = _make_state(TrailMode.SUPERTREND, stop=29000.0, high=30000.0)
    new_st = 29800.0
    update = engine.update(state, candles, st_value=new_st, direction="bullish",
                           entry_price=29000.0, mode=mode)
    assert update.new_stop >= 29000.0


def test_pct_trail_correct_calculation():
    mode_scalp = MODES["scalping"]  # trail_pct=0.5
    candles = _candles(30, base=30000.0, trend=0.0)
    state = _make_state(TrailMode.PERCENTAGE, stop=29850.0, high=30000.0)
    update = engine.update(state, candles, st_value=0.0, direction="bullish",
                           entry_price=29000.0, mode=mode_scalp)
    expected_floor = state.highest_seen * (1 - mode_scalp.trail_pct / 100.0)
    assert update.new_stop >= expected_floor - 1.0


def test_partial_25_fires_at_10pct_gain():
    candles = _candles(30, base=33100.0, trend=0.0)  # 10% above 30000
    state = TrailState(
        mode=TrailMode.ATR, current_stop=28000.0,
        highest_seen=33100.0, lowest_seen=28000.0,
    )
    update = engine.update(state, candles, st_value=28000.0, direction="bullish",
                           entry_price=30000.0, mode=mode)
    assert update.partial is not None
    assert update.partial.close_pct == 25


def test_partial_25_sets_breakeven_stop():
    candles = _candles(30, base=33100.0, trend=0.0)
    entry = 30000.0
    state = TrailState(
        mode=TrailMode.ATR, current_stop=28000.0,
        highest_seen=33100.0, lowest_seen=28000.0,
    )
    update = engine.update(state, candles, st_value=28000.0, direction="bullish",
                           entry_price=entry, mode=mode)
    assert state.breakeven_set is True
    assert state.current_stop >= entry


def test_partial_50_fires_at_20pct_gain():
    entry = 30000.0
    candles = _candles(30, base=36100.0, trend=0.0)  # ~20% above entry
    state = TrailState(
        mode=TrailMode.ATR, current_stop=entry,
        highest_seen=36100.0, lowest_seen=28000.0,
        partial_25_done=True,  # already done 25%
    )
    update = engine.update(state, candles, st_value=entry, direction="bullish",
                           entry_price=entry, mode=mode)
    assert update.partial is not None
    assert update.partial.close_pct == 25


def test_partial_50_tightens_multiplier():
    entry = 30000.0
    candles = _candles(30, base=36100.0, trend=0.0)
    old_mult = 2.0
    state = TrailState(
        mode=TrailMode.ATR, current_stop=entry,
        highest_seen=36100.0, lowest_seen=28000.0,
        partial_25_done=True, trail_mult=old_mult,
    )
    engine.update(state, candles, st_value=entry, direction="bullish",
                  entry_price=entry, mode=mode)
    assert state.trail_mult < old_mult or state.trail_mult == max(old_mult - 0.5, 1.0)


def test_30pct_milestone_locks_10pct_floor():
    entry = 30000.0
    candles = _candles(30, base=39100.0, trend=0.0)  # ~30% above entry
    state = TrailState(
        mode=TrailMode.ATR, current_stop=entry,
        highest_seen=39100.0, lowest_seen=28000.0,
        partial_25_done=True, partial_50_done=True,
    )
    engine.update(state, candles, st_value=entry, direction="bullish",
                  entry_price=entry, mode=mode)
    assert state.current_stop >= entry * 1.10


def test_stopped_out_on_low_touch():
    entry = 30000.0
    stop = 29500.0
    # Low of last candle touches stop
    candles = _candles(30, base=30000.0, trend=0.0)
    candles[-1] = Candle(
        timestamp_ms=candles[-1].timestamp_ms,
        open=30000.0, high=30100.0, low=29400.0, close=29800.0,
        volume=100.0,
    )
    state = TrailState(
        mode=TrailMode.ATR, current_stop=stop,
        highest_seen=30000.0, lowest_seen=29000.0,
    )
    update = engine.update(state, candles, st_value=stop, direction="bullish",
                           entry_price=entry, mode=mode)
    assert update.stopped_out is True


def test_trail_state_serializes_to_json():
    state = _make_state()
    s = state.to_json()
    assert isinstance(s, str)
    d = json.loads(s)
    assert "mode" in d
    assert "current_stop" in d


def test_trail_state_survives_round_trip():
    original = TrailState(
        mode=TrailMode.SUPERTREND,
        current_stop=29500.0, highest_seen=31000.0, lowest_seen=28000.0,
        partial_25_done=True, partial_50_done=False,
        breakeven_set=True, trail_mult=1.5,
    )
    serialized = original.to_json()
    restored = TrailState.from_json(serialized)
    assert restored.mode == original.mode
    assert restored.current_stop == original.current_stop
    assert restored.highest_seen == original.highest_seen
    assert restored.partial_25_done == original.partial_25_done
    assert restored.trail_mult == original.trail_mult
