"""Positions must move with the simulated clock, and an idle runner must not
present a finished session as a live one.

Both of these were reported from the running app: the dock showed a full trade
list before the user pressed play, and every trade arrived already closed with
an exit timestamped ahead of the replay clock.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.simulation import (
    SimConfig,
    SimState,
    SimStats,
    SimTradeEvent,
    SimulationRunner,
)

IST = timezone(timedelta(hours=5, minutes=30))


def _bar(symbol="NIFTY", high=100.0, low=100.0, close=100.0):
    return {"symbol": symbol, "high": high, "low": low, "close": close, "open": close, "time": 0}


def _at(hh, mm):
    return datetime(2026, 9, 4, hh, mm, tzinfo=IST)


def _open_trade(runner: SimulationRunner, *, bullish=True, entry=100.0, stop=90.0, target=130.0):
    trade = SimTradeEvent(
        trade_id="TRD-1001",
        entry_time_iso="09:20:00",
        exit_time_iso="OPEN",
        strategy="supertrend",
        symbol="NIFTY26AUG24500CE",
        underlying="NIFTY",
        direction="BUY",
        opt_type="CE" if bullish else "PE",
        strike=24_500.0,
        lots=1,
        quantity=25,
        entry_price=10.0,
        exit_price=None,
        stop_loss=7.5,
        target_price=15.0,
        status="OPEN",
        spot_entry=entry,
        spot_stop=stop,
        spot_target=target,
        raw_entry=10.0,
        bars_held=0,
    )
    runner._stats = SimStats(trades=[trade])
    runner._open_by_symbol = {"NIFTY": [trade]}
    runner._config = SimConfig(date="2026-09-04", friction_mode="ideal")
    return trade


# ── The clock ────────────────────────────────────────────────────────────────

def test_a_position_stays_open_until_a_bar_actually_reaches_its_level():
    """The defect: the outcome used to be decided from up to 30 FUTURE bars at
    the instant of entry, so a trade was born closed with an exit minutes ahead
    of the replay clock."""
    r = SimulationRunner()
    trade = _open_trade(r)

    r._settle_open_positions(_bar(high=105, low=99, close=104), _at(9, 25))

    assert trade.status == "OPEN"
    assert trade.exit_time_iso == "OPEN"
    assert trade.exit_price is None


def test_a_position_closes_on_the_bar_that_reaches_its_target():
    r = SimulationRunner()
    trade = _open_trade(r)

    r._settle_open_positions(_bar(high=105, low=99, close=104), _at(9, 25))
    r._settle_open_positions(_bar(high=131, low=104, close=130), _at(9, 30))

    assert trade.status == "WIN"
    assert trade.exit_time_iso == "09:30:00", "the exit must carry the bar's own time"
    assert trade.pnl_usd > 0


def test_a_position_closes_on_the_bar_that_reaches_its_stop():
    r = SimulationRunner()
    trade = _open_trade(r)
    r._settle_open_positions(_bar(high=101, low=89, close=92), _at(9, 30))
    assert trade.status == "LOSS"
    assert trade.pnl_usd < 0


def test_a_bar_spanning_both_levels_is_read_pessimistically():
    """A bar's high and low carry no ordering, so a bar that touches the stop
    AND the target cannot be claimed as a win."""
    r = SimulationRunner()
    trade = _open_trade(r)
    r._settle_open_positions(_bar(high=140, low=85, close=120), _at(9, 30))
    assert trade.status == "LOSS"


def test_a_short_settles_against_inverted_levels():
    r = SimulationRunner()
    trade = _open_trade(r, bullish=False, entry=100.0, stop=110.0, target=70.0)
    r._settle_open_positions(_bar(high=101, low=69, close=72), _at(9, 30))
    assert trade.status == "WIN", "a put profits when the underlying falls to target"


def test_an_open_position_is_marked_to_market_as_bars_pass():
    r = SimulationRunner()
    trade = _open_trade(r)
    r._settle_open_positions(_bar(high=115, low=100, close=114), _at(9, 25))
    assert trade.status == "OPEN"
    assert trade.pnl_usd > 0, "an in-profit open position must show unrealised gain"
    assert trade.duration_mins > 0


def test_a_position_times_out_rather_than_being_held_for_ever():
    r = SimulationRunner()
    trade = _open_trade(r)
    for i in range(SimulationRunner.MAX_HOLD_BARS):
        r._settle_open_positions(_bar(high=101, low=99, close=100), _at(9, 25))
    assert trade.status in ("WIN", "LOSS")
    assert trade.exit_time_iso != "OPEN"


def test_settling_removes_the_position_from_the_open_book():
    r = SimulationRunner()
    _open_trade(r)
    r._settle_open_positions(_bar(high=131, low=104, close=130), _at(9, 30))
    assert r._open_by_symbol.get("NIFTY") in (None, [])


def test_a_bar_for_another_symbol_does_not_settle_this_position():
    r = SimulationRunner()
    trade = _open_trade(r)
    r._settle_open_positions(_bar(symbol="RELIANCE", high=999, low=1, close=500), _at(9, 30))
    assert trade.status == "OPEN"


# ── Realised vs unrealised ───────────────────────────────────────────────────

def test_realised_pnl_excludes_positions_that_are_still_open():
    """The strip says REALIZED. Folding a mark-to-market into it would label an
    unbooked gain as money made."""
    r = SimulationRunner()
    trade = _open_trade(r)
    r._settle_open_positions(_bar(high=115, low=100, close=114), _at(9, 25))
    r._recompute_totals()
    assert trade.status == "OPEN"
    assert trade.pnl_usd > 0
    assert r._stats.pnl == 0.0

    r._settle_open_positions(_bar(high=131, low=110, close=130), _at(9, 30))
    assert r._stats.pnl > 0


def test_status_publishes_the_open_book():
    r = SimulationRunner()
    _open_trade(r)
    r._settle_open_positions(_bar(high=115, low=100, close=114), _at(9, 25))
    st = r.status
    assert st.open_positions == 1
    assert st.unrealised_pnl > 0


# ── Session identity ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_stopped_session_is_flagged_complete_not_live():
    """The reported defect: an idle runner handed every client a finished
    session's signals and trades, and the dock rendered them as though the
    replay were running — results before you pressed play."""
    r = SimulationRunner()
    _open_trade(r)
    await r.stop()
    st = r.status
    assert st.state == SimState.IDLE
    assert st.session_complete is True


@pytest.mark.asyncio
async def test_a_runner_that_never_ran_is_not_flagged_complete():
    r = SimulationRunner()
    await r.stop()
    assert r.status.session_complete is False


def test_clear_discards_the_finished_ledger():
    r = SimulationRunner()
    _open_trade(r)
    r._session_complete = True
    st = r.clear()
    assert st.stats.trades == []
    assert st.stats.events == []
    assert st.session_complete is False


def test_clear_refuses_while_a_replay_is_running():
    r = SimulationRunner()
    _open_trade(r)
    r._state = SimState.RUNNING
    r.clear()
    assert len(r._stats.trades) == 1, "a running session must not be wiped"


@pytest.mark.asyncio
async def test_stopping_leaves_end_of_session_positions_open():
    """Force-closing at the last print would book a fill the market never
    offered. The honest report is that the session ended with them open."""
    r = SimulationRunner()
    trade = _open_trade(r)
    await r.stop()
    assert trade.status == "OPEN"
    assert r._open_by_symbol == {}
