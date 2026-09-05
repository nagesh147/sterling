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


# ── Dead air at the head of a session ────────────────────────────────────────

@pytest.mark.asyncio
async def test_replay_starts_on_the_first_bar_not_the_configured_open():
    """Reported as "replay not working, clicking does nothing".

    The default session opens at 09:00 but NSE's first candle is 09:15, and the
    loop advanced the clock by `speed * dt` whether or not any data lay ahead.
    At the default 5x that is 900 simulated seconds of nothing — THREE REAL
    MINUTES of an empty dock before the first print, which is indistinguishable
    from a broken replay.
    """
    import asyncio

    runner = SimulationRunner()
    await runner.start(SimConfig(
        date="2026-09-04", start_time="09:00:00", end_time="15:30:00",
        speed=5.0, resolution="5m", instruments=["NIFTY"],
    ))

    # Give the loader a moment to hydrate and enter the loop.
    for _ in range(80):
        await asyncio.sleep(0.05)
        if runner.status.state == SimState.RUNNING and runner.status.bars_played:
            break

    st = runner.status
    await runner.stop()

    assert st.bars_total > 0, "no candles were loaded, so this proves nothing"
    assert st.bars_played > 0, "the clock was still crawling through pre-open dead air"
    # The clock must have jumped to the data rather than started at 09:00.
    assert st.current_time_iso >= "09:15:00"


# ── Session policy ───────────────────────────────────────────────────────────

def test_session_policy_follows_the_derivatives_clock_after_cas():
    """The replay drives option legs, so its close is the NFO close.

    Hardcoding 15:30 truncated every derivatives replay by ten minutes once the
    Closing Auction Session started on 2026-08-03.
    """
    r = SimulationRunner()
    r._config = SimConfig(date="2026-09-04")
    p = r.session_policy
    assert p is not None
    assert p.continuous_open == "09:15:00"
    assert p.derivatives_close == "15:40:00"
    assert p.continuous_close == p.derivatives_close
    assert p.fo_cash_close == "15:15:00", "F&O cash stops early; CAS takes over"
    assert p.cash_close == "15:30:00", "non-F&O cash is unchanged"
    assert p.cas_end == "15:35:00"
    assert p.policy_version


def test_session_policy_before_cas_keeps_the_old_close():
    """A replay of a pre-2026-08-03 date must not be given today's bounds."""
    r = SimulationRunner()
    r._config = SimConfig(date="2026-07-01")
    p = r.session_policy
    assert p is not None
    assert p.derivatives_close == "15:30:00"
    assert p.cas_end is None


def test_session_policy_is_published_on_status():
    r = SimulationRunner()
    r._config = SimConfig(date="2026-09-04")
    assert r.status.session_policy is not None
    assert r.status.session_policy.derivatives_close == "15:40:00"
