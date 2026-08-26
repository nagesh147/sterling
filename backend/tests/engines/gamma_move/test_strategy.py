"""The state machine: gate order, admission, and a trade end to end."""
from __future__ import annotations

from datetime import date

import pytest

from app.engines.gamma_move import (GammaMoveConfig, GammaMoveStrategy, Intent,
                                    SessionState, StrikeCandidate)
from tests.engines.gamma_move.conftest import BASE_MS, bar, quiet_session

TODAY = date(2026, 9, 20)
DAY = "2026-09-20"


def triggering():
    return quiet_session() + [bar(0, 24, oi=96_000, volume=5_000, close=53.0)]


def strat(**kw):
    cfg = GammaMoveConfig(enabled=True, max_premium_at_risk_inr=60_000, **kw)
    return GammaMoveStrategy(cfg, SessionState(day=DAY))


def test_arms_when_everything_holds(candidate):
    s = strat()
    sig = s.evaluate(candidate, triggering(), now_ms=BASE_MS, today=TODAY, regime="up")
    assert sig.state == "armed"
    assert sig.entry == 53.0 and sig.stop == 45.0
    assert sig.quantity and sig.quantity > 0
    assert sig.reason is None
    assert s.admit(sig, DAY) is None


def test_expiry_window_gates_before_the_trigger(candidate, instrument, level):
    """A contract outside the window must be refused without the trigger even
    being consulted -- that ordering is what keeps the request budget sane."""
    far = StrikeCandidate(underlying="RELIANCE", level=level,
                          instrument=instrument._replace(expiry="2026-12-29")
                          if hasattr(instrument, "_replace") else instrument,
                          oi=6_000_000, days_to_expiry=99, spot=1298.0, premium=53.0)
    s = strat(min_days_to_expiry=1, max_days_to_expiry=14)
    from dataclasses import replace
    far = replace(candidate, instrument=replace(candidate.instrument,
                                                expiry="2026-12-29"),
                  days_to_expiry=99)
    sig = s.evaluate(far, triggering(), now_ms=BASE_MS, today=TODAY, regime="up")
    assert sig.state == "watching"
    assert "outside" in (sig.reason or "")
    assert sig.metrics is None                # the trigger was never evaluated


def test_regime_gates_before_the_trigger(candidate):
    s = strat()
    sig = s.evaluate(candidate, triggering(), now_ms=BASE_MS, today=TODAY, regime="down")
    assert sig.state == "watching" and sig.metrics is None
    assert "uptrend" in (sig.reason or "")


def test_unknown_regime_blocks(candidate):
    s = strat()
    sig = s.evaluate(candidate, triggering(), now_ms=BASE_MS, today=TODAY,
                     regime="unknown")
    assert sig.state == "watching"


def test_incomplete_trigger_says_which_leg_is_short(candidate):
    s = strat()
    flat_oi = quiet_session() + [bar(0, 24, oi=100_000, volume=5_000, close=53.0)]
    sig = s.evaluate(candidate, flat_oi, now_ms=BASE_MS, today=TODAY, regime="up")
    assert sig.state == "watching"
    assert "open interest is not unwinding" in (sig.reason or "")
    assert sig.metrics is not None            # the numbers are still shown


def test_a_watching_row_always_has_a_reason(candidate):
    s = strat()
    for regime, bars in (("down", triggering()), ("up", quiet_session(0, 3))):
        sig = s.evaluate(candidate, bars, now_ms=BASE_MS, today=TODAY, regime=regime)
        assert sig.state != "armed"
        assert sig.reason


class TestAdmission:
    def armed(self, s, candidate):
        return s.evaluate(candidate, triggering(), now_ms=BASE_MS, today=TODAY,
                          regime="up")

    def test_disabled_strategy_refuses(self, candidate):
        s = GammaMoveStrategy(GammaMoveConfig(enabled=False,
                                              max_premium_at_risk_inr=60_000),
                              SessionState(day=DAY))
        assert s.admit(self.armed(s, candidate), DAY) == "strategy disabled"

    def test_position_cap(self, candidate):
        s = strat(max_concurrent_positions=1)
        sig = self.armed(s, candidate)
        s.on_entry(sig, 53.0, BASE_MS, DAY)
        from dataclasses import replace
        other = replace(candidate, instrument=replace(candidate.instrument,
                                                      tradingsymbol="OTHER26SEP1CE"))
        sig2 = s.evaluate(other, triggering(), now_ms=BASE_MS, today=TODAY, regime="up")
        assert "cap is 1" in (s.admit(sig2, DAY) or "")

    def test_same_contract_twice_refused(self, candidate):
        s = strat()
        sig = self.armed(s, candidate)
        s.on_entry(sig, 53.0, BASE_MS, DAY)
        assert s.admit(sig, DAY) == "already holding this contract"

    def test_daily_trade_limit(self, candidate):
        s = strat(max_new_trades_per_day=1)
        sig = self.armed(s, candidate)
        s.on_entry(sig, 53.0, BASE_MS, DAY)
        s.state.positions.clear()
        assert "daily trade limit" in (s.admit(sig, DAY) or "")

    def test_daily_loss_limit_halts(self, candidate):
        s = strat(daily_loss_limit_inr=1_000)
        sig = self.armed(s, candidate)
        pos = s.on_entry(sig, 53.0, BASE_MS, DAY)
        s.on_exit(pos, 40.0, DAY)             # -13 x 500 = -6,500
        assert s.state.halt_reason
        assert "halted" in (s.admit(sig, DAY) or "")


def test_one_trade_end_to_end(candidate):
    s = strat()
    sig = s.evaluate(candidate, triggering(), now_ms=BASE_MS, today=TODAY, regime="up")
    pos = s.on_entry(sig, 53.0, BASE_MS, DAY)
    assert s.state.positions

    # Price drifts, nothing fires.
    assert s.on_price(pos, 55.0, BASE_MS, DAY).intent is Intent.NONE
    # Through the stop.
    decision = s.on_price(pos, 44.0, BASE_MS, DAY)
    assert decision.intent is Intent.EXIT and decision.exit_reason == "stop"
    assert pos.exiting is True

    pnl = s.on_exit(pos, 44.0, DAY)
    assert pnl == pytest.approx((44.0 - 53.0) * pos.quantity)
    assert not s.state.positions
    assert s.state.record.trades == 1 and s.state.record.losses == 1


def test_only_one_exit_path_can_claim_a_position(candidate):
    """Stop, trail, target, time stop and session end are five paths to one
    position. Without the claim, two of them both send an order."""
    s = strat()
    sig = s.evaluate(candidate, triggering(), now_ms=BASE_MS, today=TODAY, regime="up")
    pos = s.on_entry(sig, 53.0, BASE_MS, DAY)
    first = s.on_price(pos, 40.0, BASE_MS, DAY)
    second = s.on_price(pos, 39.0, BASE_MS, DAY)
    assert first.intent is Intent.EXIT
    assert second.intent is Intent.NONE
