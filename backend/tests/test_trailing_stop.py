"""
Tests for the trailing stop implementation:
- ATR-based initial SL (mode-aware)
- Mode-specific partial thresholds in TrailState
- Trailing stop advances (never retreats) for longs and shorts
- Stopped-out flag fires correctly
- TP check in check_exits (spot-price based)
- Trail stop hit via check_exits current_sl
- TrailState JSON round-trip (back-compat with new fields)
"""
import json
import pytest
import numpy as np
from app.schemas.market import Candle
from app.core.trading_mode import TrailMode, MODES


def _ts(entry=50000.0, current_stop=48000.0, trail_mult=2.0, p25=0.10, p50=0.20):
    from app.engines.directional.trailing_stop import TrailState
    return TrailState(
        mode=TrailMode.ATR,
        current_stop=current_stop,
        highest_seen=entry,
        lowest_seen=entry,
        trail_mult=trail_mult,
        partial_25_pct=p25,
        partial_50_pct=p50,
    )


def _rising(n=30, base=50000.0, step=200.0):
    candles = []
    p = base
    for i in range(n):
        p += step
        candles.append(Candle(
            timestamp_ms=1_700_000_000_000 + i * 3_600_000,
            open=p - 50, high=p + 100, low=p - 100, close=p, volume=500.0,
        ))
    return candles


def _sized(direction="long"):
    from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract
    from app.schemas.directional import Direction
    leg = CandidateContract(
        instrument_name="BTC-50000-C-27DEC24",
        underlying="BTC", option_type="call", strike=50000.0,
        expiry_date="27DEC24", dte=30, mark_price=1000.0,
        bid=990.0, ask=1010.0, mid_price=1000.0, mark_iv=0.8,
        delta=0.5, open_interest=500.0, volume_24h=200.0,
        spread_pct=0.002, health_score=85.0, healthy=True,
    )
    d = Direction.LONG if direction == "long" else Direction.SHORT
    struct = TradeStructure(
        structure_type="naked_call", direction=d, legs=[leg],
        max_loss=1000.0, max_gain=None, net_premium=1000.0,
        risk_reward=2.0, score=75.0, score_breakdown={},
    )
    return SizedTrade(
        structure=struct, contracts=2, position_value=2000.0,
        max_risk_usd=500.0, capital_at_risk_pct=5.0,
    )


def _signal(direction="long", close=50100.0):
    from app.schemas.directional import SignalResult
    return SignalResult(
        trend=1 if direction == "long" else -1,
        all_green=(direction == "long"), all_red=(direction == "short"),
        green_arrow=False, red_arrow=False,
        st_trends=[1,1,1] if direction == "long" else [-1,-1,-1],
        st_values=[49000.0, 48500.0, 48000.0],
        close_1h=close, score_long=100.0, score_short=0.0,
    )


from app.schemas.execution import SizedTrade   # re-export for _sized


# ─── TrailState JSON round-trip ───────────────────────────────────────────────

class TestTrailStateJson:
    def test_roundtrip_new_fields(self):
        from app.engines.directional.trailing_stop import TrailState
        s = TrailState(
            mode=TrailMode.ATR, current_stop=48000.0,
            highest_seen=52000.0, lowest_seen=48000.0,
            trail_mult=2.0, partial_25_pct=0.08, partial_50_pct=0.15,
        )
        s2 = TrailState.from_json(s.to_json())
        assert s2.partial_25_pct == pytest.approx(0.08)
        assert s2.partial_50_pct == pytest.approx(0.15)

    def test_back_compat_old_json(self):
        """Old JSON without partial_25_pct/50_pct loads with defaults 0.10/0.20."""
        from app.engines.directional.trailing_stop import TrailState
        old = json.dumps({
            "mode": "atr", "current_stop": 48000.0,
            "highest_seen": 50000.0, "lowest_seen": 48000.0,
            "partial_25_done": False, "partial_50_done": False,
            "breakeven_set": False, "trail_mult": 2.0,
        })
        s = TrailState.from_json(old)
        assert s.partial_25_pct == pytest.approx(0.10)
        assert s.partial_50_pct == pytest.approx(0.20)


# ─── Trail advance ────────────────────────────────────────────────────────────

class TestTrailAdvance:
    def test_stop_advances_on_rising_price(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        state = _ts(entry=50000.0, current_stop=48000.0)
        update = TrailingStopEngine().update(
            state=state, candles=_rising(30), st_value=49000.0,
            direction="bullish", entry_price=50000.0, mode=MODES["swing"],
        )
        assert update.new_stop > 48000.0

    def test_stop_never_retreats(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        state = _ts(entry=50000.0, current_stop=48000.0)
        mode = MODES["swing"]
        TrailingStopEngine().update(state=state, candles=_rising(30),
            st_value=49000.0, direction="bullish", entry_price=50000.0, mode=mode)
        stop_after_rise = state.current_stop
        # Price falls back
        TrailingStopEngine().update(state=state, candles=_rising(30, 56000.0, -100.0),
            st_value=49000.0, direction="bullish", entry_price=50000.0, mode=mode)
        assert state.current_stop >= stop_after_rise

    def test_stopped_out_fires(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        state = _ts(entry=50000.0, current_stop=49500.0)
        candles = _rising(28)
        candles.append(Candle(
            timestamp_ms=candles[-1].timestamp_ms + 3_600_000,
            open=49600.0, high=49800.0, low=49400.0, close=49500.0, volume=500.0,
        ))
        update = TrailingStopEngine().update(
            state=state, candles=candles, st_value=49000.0,
            direction="bullish", entry_price=50000.0, mode=MODES["swing"],
        )
        assert update.stopped_out is True

    def test_short_stop_advances_downward(self):
        from app.engines.directional.trailing_stop import TrailState, TrailingStopEngine
        state = TrailState(
            mode=TrailMode.ATR, current_stop=52000.0,
            highest_seen=50000.0, lowest_seen=50000.0,
            trail_mult=2.0,
        )
        falling = []
        p = 50000.0
        for i in range(30):
            p -= 200.0
            falling.append(Candle(
                timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                open=p + 50, high=p + 100, low=p - 100, close=p, volume=500.0,
            ))
        update = TrailingStopEngine().update(
            state=state, candles=falling, st_value=52000.0,
            direction="bearish", entry_price=50000.0, mode=MODES["swing"],
        )
        assert update.new_stop < 52000.0

    def test_current_tp_echoed_back(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        state = _ts()
        update = TrailingStopEngine().update(
            state=state, candles=_rising(30), st_value=49000.0,
            direction="bullish", entry_price=50000.0, mode=MODES["swing"],
            initial_tp=56000.0,
        )
        assert update.current_tp == pytest.approx(56000.0)


# ─── Mode-aware partial thresholds ───────────────────────────────────────────

class TestModePartials:
    def _at_gain(self, base, pct, n=30):
        target = base * (1 + pct)
        step   = (target - base) / n
        candles = []
        p = base
        for i in range(n):
            p += step
            candles.append(Candle(
                timestamp_ms=1_700_000_000_000 + i * 3_600_000,
                open=p - 10, high=p + 20, low=p - 20, close=p, volume=500.0,
            ))
        return candles

    def test_scalp_partial_at_5pct(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        entry = 50000.0
        state = _ts(entry=entry, current_stop=entry * 0.98, p25=0.05, p50=0.10)
        update = TrailingStopEngine().update(
            state=state, candles=self._at_gain(entry, 0.07),
            st_value=entry * 0.97, direction="bullish",
            entry_price=entry, mode=MODES["scalping"],
        )
        assert update.partial is not None
        assert state.partial_25_done is True
        assert state.breakeven_set is True

    def test_swing_partial_at_10pct(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        entry = 50000.0
        state = _ts(entry=entry, current_stop=entry * 0.95, p25=0.10, p50=0.20)
        update = TrailingStopEngine().update(
            state=state, candles=self._at_gain(entry, 0.12),
            st_value=entry * 0.94, direction="bullish",
            entry_price=entry, mode=MODES["swing"],
        )
        assert update.partial is not None
        assert state.partial_25_done is True

    def test_no_partial_below_threshold(self):
        from app.engines.directional.trailing_stop import TrailingStopEngine
        entry = 50000.0
        state = _ts(entry=entry, current_stop=entry * 0.95, p25=0.10, p50=0.20)
        update = TrailingStopEngine().update(
            state=state, candles=self._at_gain(entry, 0.05),
            st_value=entry * 0.94, direction="bullish",
            entry_price=entry, mode=MODES["swing"],
        )
        assert update.partial is None


# ─── check_exits: spot-price TP / SL ─────────────────────────────────────────

class TestCheckExitsSlTp:
    def test_tp_hit_long(self):
        from app.engines.directional.monitor_engine import check_exits
        s = _sized("long"); sig = _signal("long")
        r = check_exits(s, sig, 0.0, 20, current_spot=56000.0, current_tp=55000.0)
        assert r.should_exit and r.exit_type == "full_profit" and "profit" in r.reason.lower()

    def test_tp_not_hit_long(self):
        from app.engines.directional.monitor_engine import check_exits
        s = _sized("long"); sig = _signal("long")
        r = check_exits(s, sig, 0.0, 20, current_spot=52000.0, current_tp=55000.0)
        assert not r.should_exit

    def test_tp_hit_short(self):
        from app.engines.directional.monitor_engine import check_exits
        s = _sized("short"); sig = _signal("short", close=44000.0)
        r = check_exits(s, sig, 0.0, 20, current_spot=44000.0, current_tp=45000.0)
        assert r.should_exit and r.exit_type == "full_profit"

    def test_sl_hit_long(self):
        from app.engines.directional.monitor_engine import check_exits
        s = _sized("long"); sig = _signal("long", close=47000.0)
        r = check_exits(s, sig, 0.0, 20, current_spot=47000.0, current_sl=48000.0)
        assert r.should_exit and r.exit_type == "trail_stop"

    def test_sl_hit_short(self):
        from app.engines.directional.monitor_engine import check_exits
        s = _sized("short"); sig = _signal("short", close=53000.0)
        r = check_exits(s, sig, 0.0, 20, current_spot=53000.0, current_sl=52000.0)
        assert r.should_exit and r.exit_type == "trail_stop"

    def test_sl_tp_none_no_spurious_exit(self):
        from app.engines.directional.monitor_engine import check_exits
        s = _sized("long"); sig = _signal("long")
        r = check_exits(s, sig, 0.0, 20, current_spot=51000.0)
        assert not r.should_exit

    def test_sl_priority_over_thesis(self):
        """Trail stop (priority 3) fires before thesis stop (priority 4)."""
        from app.engines.directional.monitor_engine import check_exits
        from app.schemas.directional import SignalResult
        s = _sized("long")
        sig_bearish = SignalResult(
            trend=-1, all_green=False, all_red=True,
            green_arrow=False, red_arrow=False,
            st_trends=[-1,-1,-1], st_values=[0.0,0.0,0.0],
            close_1h=47000.0, score_long=0.0, score_short=100.0,
        )
        r = check_exits(s, sig_bearish, 0.0, 20,
                        current_spot=47000.0, current_sl=48000.0)
        assert r.exit_type == "trail_stop"


# ─── Initial SL/TP formula ────────────────────────────────────────────────────

class TestSlTpFormula:
    def test_long_sl_below_entry_tp_above(self):
        entry = 50000.0; atr = 1500.0
        for mode in MODES.values():
            dist = mode.stop_atr_mult * atr
            sl = entry - dist; tp = entry + mode.rr_target * dist
            assert sl < entry and tp > entry
            rr = (tp - entry) / (entry - sl)
            assert rr == pytest.approx(mode.rr_target, rel=1e-9)

    def test_short_sl_above_entry_tp_below(self):
        entry = 50000.0; atr = 1500.0
        for mode in MODES.values():
            dist = mode.stop_atr_mult * atr
            sl = entry + dist; tp = entry - mode.rr_target * dist
            assert sl > entry and tp < entry
            rr = (entry - tp) / (sl - entry)
            assert rr == pytest.approx(mode.rr_target, rel=1e-9)


# ─── paper_store.add_position SL/TP persistence ──────────────────────────────

class TestAddPositionSlTp:
    def _make_sized(self):
        from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract
        from app.schemas.directional import Direction
        leg = CandidateContract(
            instrument_name="BTC-50000-C-27DEC24",
            underlying="BTC", option_type="call", strike=50000.0,
            expiry_date="27DEC24", dte=30, mark_price=1000.0,
            bid=990.0, ask=1010.0, mid_price=1000.0, mark_iv=0.8,
            delta=0.5, open_interest=500.0, volume_24h=200.0,
            spread_pct=0.002, health_score=85.0, healthy=True,
        )
        struct = TradeStructure(
            structure_type="naked_call", direction=Direction.LONG, legs=[leg],
            max_loss=1000.0, max_gain=None, net_premium=1000.0,
            risk_reward=2.0, score=75.0, score_breakdown={},
        )
        return SizedTrade(structure=struct, contracts=2, position_value=2000.0,
                          max_risk_usd=500.0, capital_at_risk_pct=5.0)

    def test_sl_tp_stored_from_params(self):
        from app.services import paper_store as ps
        sized = self._make_sized()
        pos = ps.add_position("BTC", sized, entry_spot_price=50000.0,
                              initial_sl=47000.0, initial_tp=56000.0)
        assert pos.initial_sl == pytest.approx(47000.0)
        assert pos.current_sl == pytest.approx(47000.0)
        assert pos.initial_tp == pytest.approx(56000.0)
        assert pos.current_tp == pytest.approx(56000.0)
        del ps._positions[pos.id]

    def test_fallback_no_sl(self):
        from app.services import paper_store as ps
        from app.engines.directional.trailing_stop import TrailState
        sized = self._make_sized()
        pos = ps.add_position("BTC", sized, entry_spot_price=50000.0)
        trail = TrailState.from_json(pos.trail_stop_json)
        assert trail.current_stop == pytest.approx(50000.0 * 0.95, rel=0.01)
        del ps._positions[pos.id]

    def test_mode_partials_in_trail_state(self):
        from app.services import paper_store as ps
        from app.engines.directional.trailing_stop import TrailState
        sized = self._make_sized()
        for mode_name, mode in MODES.items():
            pos = ps.add_position("BTC", sized, entry_spot_price=50000.0,
                                  trail_mode_name=mode_name)
            trail = TrailState.from_json(pos.trail_stop_json)
            assert trail.partial_25_pct == pytest.approx(mode.partial_25_pct)
            assert trail.partial_50_pct == pytest.approx(mode.partial_50_pct)
            del ps._positions[pos.id]
