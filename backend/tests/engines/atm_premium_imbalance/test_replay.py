"""Bar-level replay harness.

These tests use fixture bars so the harness is trustworthy *before* it is pointed
at Kite. The point of a replay is to be able to disagree with the recording, so
there is a negative test for every positive one.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, InstrumentRef, OptionPairRef,
)
from app.engines.atm_premium_imbalance.conformance import MATCH, MISMATCH, UNVERIFIED
from app.engines.atm_premium_imbalance.replay import (
    Bar, ObservedSession, first_bar_reaching, open_bar, replay_session, session_bars,
)

IST = timezone(timedelta(hours=5, minutes=30))
SESSION = date(2026, 8, 20)


def bar(hh, mm, o, h=None, l=None, c=None):
    return Bar(datetime(2026, 8, 20, hh, mm, tzinfo=IST), o,
               h if h is not None else o, l if l is not None else o,
               c if c is not None else o)


def pair(strike=77500.0):
    def ref(ot, token):
        return InstrumentRef(instrument_id=token, tradingsymbol=f"SENSEX2682077500{ot}",
                             option_type=ot, strike=strike, expiry="2026-08-20",
                             lot_size=20, tick_size=0.05, exchange="BFO")
    return OptionPairRef(underlying="SENSEX", expiry="2026-08-20", strike=strike,
                         ce=ref("CE", "219005189"), pe=ref("PE", "218831109"))


def cfg():
    return ATMPremiumImbalanceConfig(
        enabled=True, quantity=100,
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10,
        expiry_policy="NEAREST",
    ).validate()


OBSERVED = ObservedSession(
    label="V1", session=SESSION, expiry="2026-08-20", strike=77500.0, option_type="CE",
    first_tick_price=102.85, entry_order_price=113.10, entry_fill=113.10,
    exit_order_price=126.60, exit_fill=126.60, quantity=100, index_at_open=77510.0,
)

#: CE bars consistent with the recording: opens at 102.85, dips, then reaches the
#: 128.10 target in the 09:24 minute, whose range brackets the 126.60 exit fill.
CE_BARS = [
    bar(9, 15, 102.85, 118.00, 95.10, 116.00),
    bar(9, 16, 116.00, 120.00, 94.60, 95.60),
    bar(9, 24, 126.35, 128.60, 125.90, 127.10),
]
PE_BARS = [
    bar(9, 15, 168.25, 240.00, 163.00, 219.25),
    bar(9, 16, 219.25, 237.80, 210.00, 220.15),
    bar(9, 24, 168.25, 169.00, 163.60, 164.00),
]
INDEX_BARS = [bar(9, 15, 77510.0, 77600.0, 77480.0, 77560.0)]
LISTED = [77300.0, 77400.0, 77500.0, 77600.0, 77700.0]


# ------------------------------------------------------------------ helpers

def test_open_bar_and_session_bars():
    assert open_bar(CE_BARS, SESSION).open == 102.85
    assert open_bar(CE_BARS, date(2026, 8, 21)) is None
    assert len(session_bars(CE_BARS, SESSION)) == 3


def test_first_bar_reaching_needs_the_high_to_reach_the_target():
    after = CE_BARS[0].ts
    assert first_bar_reaching(CE_BARS, 128.10, after=after).ist.hour == 9
    assert first_bar_reaching(CE_BARS, 128.10, after=after).ist.minute == 24
    assert first_bar_reaching(CE_BARS, 500.0, after=after) is None
    # the open bar itself is excluded: entry happens inside it
    assert first_bar_reaching(CE_BARS, 118.00, after=after).ist.minute == 16


# ----------------------------------------------------------------- positive

def test_replay_agrees_with_the_recording_on_every_checkable_field():
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=CE_BARS, pe_bars=PE_BARS,
                         index_bars=INDEX_BARS, listed_strikes=LISTED, pair=pair())
    by = {c.field: c for c in res.checks}
    assert res.mismatch == 0, res.table()

    assert by["index_at_open"].verdict == MATCH
    assert by["atm_strike"].verdict == MATCH            # 77510 -> 77500
    assert by["option_type"].verdict == MATCH           # CE 102.85 < PE 168.25
    assert by["first_tick_price"].verdict == MATCH      # 09:15 open
    assert by["entry_order_price"].verdict == MATCH     # 102.85 x 1.10 -> 113.1
    assert by["entry_fill_within_open_bar"].verdict == MATCH
    assert by["target_reached"].verdict == MATCH
    assert by["target_reached"].replayed == "09:24 IST"
    assert by["exit_fill_within_target_bar"].verdict == MATCH
    # and the decision came from the real engine, not from arithmetic here
    assert by["engine_option_type"].verdict == MATCH
    # this recording had no stale-tick fault, so agreeing with the recording and
    # agreeing with the market are the same thing
    assert by["engine_vs_recording"].verdict == MATCH
    assert by["engine_vs_market"].verdict == MATCH
    assert res.engine_summary["entry_order_price"] == 113.10
    # the bar quotes are dated, so the session-origin gate is genuinely exercised
    # here rather than skipped as "undatable"
    assert res.engine_summary["state"] in ("open", "closed", "entry_pending")


def test_a_stale_price_fed_first_is_rejected_and_the_session_open_is_used():
    """Reproduces the 2026-08-21 feed order with this fixture's prices.

    A carried-over 150.00 arrives before the real 102.85 open. The engine must
    ignore it: pricing from 150.00 would give 165.0, from 102.85 gives 113.1.
    """
    from datetime import datetime as _dt
    prior = int(_dt(2026, 8, 19, 15, 33, tzinfo=IST).timestamp() * 1000)
    obs = ObservedSession(**{**OBSERVED.__dict__,
                             "stale_price": 150.00, "stale_traded_at_ms": prior})
    res = replay_session(obs, cfg=cfg(), ce_bars=CE_BARS, pe_bars=PE_BARS,
                         index_bars=INDEX_BARS, listed_strikes=LISTED, pair=pair())
    by = {c.field: c for c in res.checks}
    assert by["stale_price_rejected"].verdict == MATCH
    assert by["engine_vs_market"].verdict == MATCH
    assert res.engine_summary["entry_order_price"] == 113.10      # not 165.0


# ----------------------------------------------------------------- negative

def test_a_disagreeing_first_tick_is_reported_not_absorbed():
    bars = [bar(9, 15, 150.00, 160.0, 149.0, 155.0)] + CE_BARS[1:]
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=bars, pe_bars=PE_BARS,
                         index_bars=INDEX_BARS, listed_strikes=LISTED, pair=pair())
    by = {c.field: c for c in res.checks}
    assert by["first_tick_price"].verdict == MISMATCH
    assert by["entry_order_price"].verdict == MISMATCH   # 150 x 1.10 != 113.1
    # we still agree with the market -- it is the recording that is out
    assert by["engine_vs_market"].verdict == MATCH
    assert by["engine_vs_recording"].verdict == MISMATCH
    assert res.contradicted is True


def test_a_target_never_reached_is_a_mismatch():
    bars = [CE_BARS[0], bar(9, 16, 100.0, 105.0, 95.0, 98.0)]
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=bars, pe_bars=PE_BARS,
                         index_bars=INDEX_BARS, listed_strikes=LISTED, pair=pair())
    by = {c.field: c for c in res.checks}
    assert by["target_reached"].verdict == MISMATCH
    assert by["target_reached"].replayed is None


def test_a_fill_outside_its_bar_is_a_mismatch():
    """The one thing bars *can* say about a fill: whether it is even possible."""
    obs = ObservedSession(**{**OBSERVED.__dict__, "entry_fill": 500.0})
    res = replay_session(obs, cfg=cfg(), ce_bars=CE_BARS, pe_bars=PE_BARS,
                         index_bars=INDEX_BARS, listed_strikes=LISTED, pair=pair())
    by = {c.field: c for c in res.checks}
    assert by["entry_fill_within_open_bar"].verdict == MISMATCH


def test_the_wrong_leg_being_cheaper_is_reported():
    """If the real bars say the PUT was cheaper, a CE recording is contradicted."""
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=PE_BARS, pe_bars=CE_BARS,
                         index_bars=INDEX_BARS, listed_strikes=LISTED, pair=pair())
    by = {c.field: c for c in res.checks}
    assert by["option_type"].verdict == MISMATCH


# ---------------------------------------------------------------- unverified

def test_missing_option_bars_are_unverified_not_a_pass():
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=[], pe_bars=[], pair=pair())
    assert res.match == 0 and res.mismatch == 0
    assert res.unverified == 1
    assert res.checks[0].field == "option_bars"


def test_a_missing_open_bar_is_unverified():
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=CE_BARS[1:], pe_bars=PE_BARS[1:], pair=pair())
    assert res.mismatch == 0
    assert any(c.field == "open_bar" and c.verdict == UNVERIFIED for c in res.checks)


def test_fields_the_recording_never_printed_stay_unverified():
    """2026-08-21 printed no exit; the replay must not invent one."""
    obs = ObservedSession(label="V0821", session=SESSION, expiry="2026-08-20",
                          strike=77500.0, option_type="CE", first_tick_price=102.85,
                          entry_order_price=113.10, quantity=100)
    res = replay_session(obs, cfg=cfg(), ce_bars=CE_BARS, pe_bars=PE_BARS, pair=pair())
    fields = {c.field for c in res.checks}
    assert "exit_fill_within_target_bar" not in fields
    assert "target_reached" not in fields          # no fill -> no target to check


def test_the_report_states_the_granularity_limit():
    res = replay_session(OBSERVED, cfg=cfg(), ce_bars=CE_BARS, pe_bars=PE_BARS, pair=pair())
    joined = " ".join(res.notes)
    assert "Minute bars only" in joined
    assert "tick ordering is not testable" in joined
