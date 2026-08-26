"""Stops, exits and size — including the three ways size can legitimately be zero."""
from __future__ import annotations

import pytest

from app.engines.gamma_move import (GammaMoveConfig, PositionState, TradeRecord,
                                    exit_order_price, initial_stop, lots_for,
                                    realised_inr, risk_multiplier, should_exit,
                                    sizing_blocker, swing_low_stop, target_price,
                                    update_trail)
from tests.engines.gamma_move.conftest import bar

CFG = GammaMoveConfig()


def series(low=45.0, close=50.0, n=8):
    return [bar(0, i, close=close, low=low) for i in range(n)]


def test_stop_is_the_options_own_swing_low():
    assert swing_low_stop(series(low=45.0), CFG) == 45.0


def test_percent_floor_caps_a_far_swing_low():
    """A swing low 70% below entry is a stop in name only; the tighter wins."""
    stop = initial_stop(100.0, series(low=30.0), CFG)
    assert stop == 70.0                      # the 30% floor, not the 30.0 swing low


def test_swing_low_wins_when_it_is_tighter():
    assert initial_stop(100.0, series(low=90.0), CFG) == 90.0


def test_inverted_stop_is_a_rejected_setup():
    """Never entered with the stop quietly moved somewhere it can be honoured."""
    assert initial_stop(50.0, series(low=60.0), CFG) is None


def test_target_only_under_percent_target():
    assert target_price(100.0, CFG) is None
    cfg = GammaMoveConfig(exit_policy="PERCENT_TARGET", target_pct=50)
    assert target_price(100.0, cfg) == 150.0


def position(**kw):
    base = dict(signal_id="s", instrument=None, entry=100.0, stop=70.0, quantity=500,
                lots=1, entered_ms=0, entry_day="2026-09-20")
    base.update(kw)
    return PositionState(**base)


def test_stop_fires_before_anything_else():
    assert should_exit(position(), 69.0, 0, "2026-09-20", CFG) == "stop"


def test_time_stop_counts_sessions_not_hours():
    """A weekend must not age a position by two."""
    pos = position()
    assert should_exit(pos, 100.0, 0, "2026-09-20", CFG) is None   # same day
    pos.sessions_held = 1
    assert should_exit(pos, 100.0, 0, "2026-09-21", CFG) is None   # one session
    pos.sessions_held = 2
    assert should_exit(pos, 100.0, 0, "2026-09-22", CFG) == "time_stop"


def test_trail_only_ratchets_up():
    cfg = GammaMoveConfig(exit_policy="TRAILING_STOP", trail_pct=20, stop_percent=30)
    pos = position()
    update_trail(pos, 200.0, cfg)
    first = pos.trail
    update_trail(pos, 120.0, cfg)             # price falls back
    assert pos.trail == first                 # the trail does not follow it down


def test_trail_waits_for_the_start_threshold():
    cfg = GammaMoveConfig(exit_policy="TRAILING_STOP", trail_pct=20, trail_start_pct=50)
    pos = position()
    update_trail(pos, 120.0, cfg)             # only +20%
    assert pos.trail is None
    update_trail(pos, 160.0, cfg)             # +60%, past the start
    assert pos.trail is not None


def test_exit_price_aligns_to_the_tick():
    assert exit_order_price(53.037, 0.05) == 53.05


def test_realised_is_per_unit_times_quantity():
    assert realised_inr(position(), 110.0) == 5000.0


class TestSizing:
    def test_risk_budget_sets_the_size(self):
        # 1% of 500,000 = 5,000; risk per unit 10 x lot 500 = 5,000 -> 1 lot
        assert lots_for(50.0, 40.0, 500, CFG) == 1

    def test_premium_outlay_cap_can_bind_instead(self):
        cfg = GammaMoveConfig(max_premium_at_risk_inr=20_000)
        assert lots_for(53.0, 45.0, 500, cfg) == 0
        assert "outlay cap" in (sizing_blocker(53.0, 45.0, 500, cfg) or "")

    def test_risk_budget_blocker_names_the_budget(self):
        cfg = GammaMoveConfig(capital_inr=10_000)
        assert "risk budget" in (sizing_blocker(50.0, 40.0, 500, cfg) or "")

    def test_inverted_stop_blocker(self):
        assert "not below entry" in (sizing_blocker(40.0, 50.0, 500, CFG) or "")

    def test_no_blocker_when_the_size_is_fine(self):
        assert sizing_blocker(50.0, 40.0, 500, CFG) is None


class TestDescaleLadder:
    """The one risk rule the source actually states."""

    @staticmethod
    def rec(*pnls):
        r = TradeRecord()
        for p in pnls:
            r.record(p, "d", descale_after=CFG.descale_after_losses,
                     rescale_after=CFG.rescale_after_wins)
        return r

    def test_full_size_until_the_streak(self):
        assert risk_multiplier(self.rec(-100, -100), CFG) == 1.0

    def test_halves_at_the_threshold(self):
        assert risk_multiplier(self.rec(-100, -100, -100), CFG) == 0.5

    def test_one_winner_does_not_restore_full_size(self):
        """A single win resets the loss streak, so a multiplier derived from the
        live streak would put full size back on mid-run. The flag latches."""
        assert risk_multiplier(self.rec(-100, -100, -100, 100), CFG) == 0.5

    def test_restores_after_the_required_wins(self):
        assert risk_multiplier(self.rec(-100, -100, -100, 100, 100), CFG) == 1.0

    def test_relapses_on_a_fresh_streak(self):
        r = self.rec(-100, -100, -100, 100, 100, -100, -100, -100)
        assert risk_multiplier(r, CFG) == 0.5

    def test_descaling_actually_shrinks_the_order(self):
        r = self.rec(-100, -100, -100)
        big = GammaMoveConfig(capital_inr=5_000_000, max_premium_at_risk_inr=10_000_000)
        assert lots_for(50.0, 40.0, 500, big, r) < lots_for(50.0, 40.0, 500, big)
