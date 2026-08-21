"""The operator's terminal log.

This strategy makes one decision a day, in the first seconds of the session. The
log has to show that decision and the two orders that follow — and it has to do
it without printing the premium comparison on every one of thousands of ticks.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import ATMPremiumImbalanceConfig
import app.services.atm_premium_imbalance_runner as R

from tests.services.test_atm_premium_imbalance_runner import (  # noqa: F401
    FakeBroker, _pair, _session, tick,
)

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    from app.services.kite_engine import state
    state._activity.clear()
    R.clear()
    monkeypatch.setattr(R, "_is_market_open", lambda: True)
    yield
    state._activity.clear()
    R.clear()


def lines(uid="u1"):
    from app.services.kite_engine import state
    return [(e.kind, e.message) for e in state.activity(uid)]


def kinds(uid="u1"):
    return [k for k, _ in lines(uid)]


@pytest.mark.asyncio
async def test_a_full_trade_reads_as_a_story():
    """signal -> entry -> fill -> exit -> done, in that order."""
    s = _session(); R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=156.85)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)

    order = kinds()
    for expected in ("api_signal", "api_entry", "api_filled", "api_exit", "api_done"):
        assert expected in order, order
    assert order.index("api_signal") < order.index("api_entry")
    assert order.index("api_entry") < order.index("api_filled")
    assert order.index("api_filled") < order.index("api_exit")
    assert order.index("api_exit") < order.index("api_done")


@pytest.mark.asyncio
async def test_the_signal_line_shows_the_comparison_it_decided_on():
    """The premium comparison *is* the strategy; a log without it is useless."""
    s = _session(); R.register(s)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], FakeBroker())
    msg = next(m for k, m in lines() if k == "api_signal")
    assert "CE 167.50" in msg and "PE 214.85" in msg
    assert "diff 47.35" in msg
    assert "buy the CE" in msg


@pytest.mark.asyncio
async def test_the_done_line_carries_the_result():
    s = _session(); R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=156.85)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    msg = next(m for k, m in lines() if k == "api_done")
    assert "+23.45 pts" in msg
    assert "469" in msg


@pytest.mark.asyncio
async def test_a_refusal_is_said_once_not_on_every_tick():
    """A reason that stays true for an hour must not fill the terminal."""
    s = _session(); R.register(s)
    b = FakeBroker()
    for _ in range(25):
        # equal premiums: refused, forever, on every tick
        await R.on_ticks("u1", [tick(111, 200.0, 199.5, 200.5),
                                tick(222, 200.0, 199.5, 200.5)], b)
    waiting = [m for k, m in lines() if k == "api_waiting"]
    assert len(waiting) == 1
    assert "CE and PE are equal" in waiting[0]


@pytest.mark.asyncio
async def test_a_changed_reason_is_reported_again():
    """Deduping must not hide a *different* reason arriving."""
    s = _session(); R.register(s)
    b = FakeBroker()
    await R.on_ticks("u1", [tick(111, 200.0, 199.5, 200.5),
                            tick(222, 200.0, 199.5, 200.5)], b)
    s.strategy.trades_taken = 5           # now refused for another reason
    await R.on_ticks("u1", [tick(111, 200.0, 199.5, 200.5),
                            tick(222, 180.0, 179.5, 180.5)], b)
    waiting = [m for k, m in lines() if k == "api_waiting"]
    assert len(waiting) == 2
    assert "already traded this session" in waiting[1]


@pytest.mark.asyncio
async def test_refusal_reasons_are_in_plain_language():
    """"stale_session_quote" tells an operator nothing at a glance."""
    assert R._refusal_text("stale_session_quote") == "a quote traded before today's open"
    assert R._refusal_text("entry_window_closed") == "too long after the open"


@pytest.mark.asyncio
async def test_an_unmapped_reason_is_shown_rather_than_swallowed():
    """A new refusal reason must be visible the day it is added."""
    assert R._refusal_text("some_new_gate") == "some_new_gate"
    assert R._refusal_text(None) == "no reason given"


@pytest.mark.asyncio
async def test_a_moving_stop_is_reported_when_it_moves_and_not_otherwise():
    cfg = ATMPremiumImbalanceConfig(
        enabled=True, quantity=20, exit_policy="TRAILING_STOP", stop_enabled=True,
        stop_basis="PERCENT", stop_percent=20.0, trail_percent=10.0,
        trail_start_percent=5.0, breakeven_percent=3.0, target_points=0.0,
        max_premium_at_risk_inr=40_000.0).validate()
    s = _session(); s.strategy.cfg = cfg; R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=200.0)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    # a flat market moves nothing
    for _ in range(5):
        await R.on_ticks("u1", [tick(111, 140.0, 139.5, 140.5)], b)
    first = [m for k, m in lines() if k == "api_stop"]
    # then a run up ratchets it
    await R.on_ticks("u1", [tick(111, 170.0, 169.5, 170.5)], b)
    after = [m for k, m in lines() if k == "api_stop"]
    assert len(after) > len(first), "a ratcheted stop should be reported"
    assert "peak 170.00" in after[-1]


@pytest.mark.asyncio
async def test_a_halt_says_why():
    s = _session(quantity=80); R.register(s)
    s.strategy.cfg = ATMPremiumImbalanceConfig(
        enabled=True, quantity=80, max_premium_at_risk_inr=1_000.0).validate()
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], FakeBroker())
    msg = next(m for k, m in lines() if k == "api_halt")
    assert "premium_at_risk_exceeded" in msg


@pytest.mark.asyncio
async def test_a_rejected_order_is_reported():
    s = _session(); R.register(s)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], FakeBroker(fail_place=True))
    assert any(k == "api_order_failed" and "broker down" in m for k, m in lines())


def test_logging_never_breaks_a_trade(monkeypatch):
    """A log line is not worth an exception on the order path."""
    from app.services.kite_engine import state

    def boom(*a, **k):
        raise RuntimeError("log backend gone")
    monkeypatch.setattr(state, "log", boom)
    R.note("u1", "api_entry", "anything")        # must not raise


@pytest.mark.asyncio
async def test_a_peak_that_moves_without_the_stop_is_not_news():
    """The stop line reports the stop. A rising peak that leaves the stop where
    it was is context, not an event, and reporting it fills the terminal.
    """
    cfg = ATMPremiumImbalanceConfig(
        enabled=True, quantity=20, exit_policy="TRAILING_STOP", stop_enabled=True,
        stop_basis="PERCENT", stop_percent=20.0, trail_percent=10.0,
        trail_start_percent=50.0, breakeven_percent=50.0, target_points=0.0,
        max_premium_at_risk_inr=40_000.0).validate()
    s = _session(); s.strategy.cfg = cfg; R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=500.0)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    # the peak climbs, but 50% triggers keep every rung out of reach
    for px in (140.0, 150.0, 160.0, 170.0):
        await R.on_ticks("u1", [tick(111, px, px - 0.5, px + 0.5)], b)
    stops = [m for k, m in lines() if k == "api_stop"]
    assert len(stops) == 1, stops

