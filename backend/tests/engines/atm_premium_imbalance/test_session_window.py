"""The trading window.

Two rules that were config fields nothing read:

* an entry may only be taken near the open, because "buys the cheaper ATM leg at
  the open" is what this strategy *is* — the same code entering at 14:00 is a
  different strategy wearing the same name
* a position must not outlive the session, because a bought option held to
  expiry can settle worthless
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, LegQuote,
)
from app.engines.atm_premium_imbalance.session import (
    session_close_ms_for, session_open_ms_for,
)

from .test_golden_trades import make_pair

IST = timezone(timedelta(hours=5, minutes=30))
# 2026-08-21, a real trading day.
OPEN_MS = int(datetime(2026, 8, 21, 9, 15, tzinfo=IST).timestamp() * 1000)
CLOSE_MS = int(datetime(2026, 8, 21, 15, 25, tzinfo=IST).timestamp() * 1000)


def _strategy(**kw):
    base = dict(enabled=True, quantity=20, target_points=15.0,
                max_premium_at_risk_inr=40_000.0)
    base.update(kw)
    cfg = ATMPremiumImbalanceConfig(**base).validate()
    return ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=make_pair(77700.0, "ACE", "APE", "2026-08-27", upper=3000.0),
        quantity=20, trade_id="t")


def _tick(s, leg, ltp, bid, ask, at_ms):
    inst = s.pair.ce.instrument_id if leg == "CE" else s.pair.pe.instrument_id
    return s.on_option_tick(
        LegQuote(instrument_id=inst, ltp=ltp, bid=bid, ask=ask,
                 exchange_ts_ms=at_ms, received_ts_ms=at_ms, sequence=at_ms),
        at_ms)


# -------------------------------------------------------------- the arithmetic

def test_the_close_stamp_lands_on_the_configured_time():
    midday = OPEN_MS + 3 * 3600 * 1000
    assert session_close_ms_for(midday, "15:25") == CLOSE_MS


def test_open_and_close_are_anchored_on_the_same_ist_day():
    """A UTC-anchored close would roll over mid-session for no useful reason."""
    late = OPEN_MS + 6 * 3600 * 1000                 # 15:15 IST, past 09:45 UTC
    assert session_open_ms_for(late, "09:15") == OPEN_MS
    assert session_close_ms_for(late, "15:25") == CLOSE_MS


# ------------------------------------------------------------- the entry window

def test_an_entry_at_the_open_is_taken():
    s = _strategy()
    _tick(s, "CE", 491.15, 490.5, 491.6, OPEN_MS + 500)
    assert _tick(s, "PE", 337.15, 336.6, 337.6, OPEN_MS + 900).kind == "submit_entry"


def test_an_entry_hours_after_the_open_is_refused():
    """This is the finding: without a window it would simply trade at 14:00."""
    s = _strategy()
    late = OPEN_MS + 5 * 3600 * 1000
    _tick(s, "CE", 491.15, 490.5, 491.6, late)
    intent = _tick(s, "PE", 337.15, 336.6, 337.6, late + 400)
    assert intent.kind == "none"
    assert intent.reason == "entry_window_closed"
    assert s.trade is None


def test_the_window_edge_is_inclusive_of_the_last_second():
    s = _strategy(entry_window_seconds=300)
    edge = OPEN_MS + 300 * 1000
    _tick(s, "CE", 491.15, 490.5, 491.6, edge - 1)
    assert _tick(s, "PE", 337.15, 336.6, 337.6, edge).kind == "submit_entry"


def test_one_second_past_the_window_is_refused():
    s = _strategy(entry_window_seconds=300)
    past = OPEN_MS + 300 * 1000 + 1
    _tick(s, "CE", 491.15, 490.5, 491.6, past)
    assert _tick(s, "PE", 337.15, 336.6, 337.6, past).reason == "entry_window_closed"


def test_a_zero_window_means_no_window():
    """Kept expressible so the pre-window behaviour can still be replayed."""
    s = _strategy(entry_window_seconds=0)
    late = OPEN_MS + 5 * 3600 * 1000
    _tick(s, "CE", 491.15, 490.5, 491.6, late)
    assert _tick(s, "PE", 337.15, 336.6, 337.6, late).kind == "submit_entry"


def test_a_pre_open_tick_is_not_treated_as_late():
    """now_ms before the open is negative elapsed, not a closed window."""
    s = _strategy()
    before = OPEN_MS - 60_000
    _tick(s, "CE", 491.15, 490.5, 491.6, before)
    assert _tick(s, "PE", 337.15, 336.6, 337.6, before).kind == "submit_entry"


# --------------------------------------------------------- the session-end exit

def _in_position():
    """A filled position, entered at the open."""
    from .test_golden_trades import ScriptedBroker
    s = _strategy()
    b = ScriptedBroker(entry_fill=340.10, exit_fill=356.00)
    intent = _tick(s, "CE", 491.15, 490.5, 491.6, OPEN_MS + 500)
    intent = _tick(s, "PE", 337.15, 336.6, 337.6, OPEN_MS + 900)
    while intent.kind not in ("none", "complete", "halt"):
        intent = b.run(s, intent)
    assert s.phase.value == "in_position", s.phase
    return s, b


def test_the_position_is_closed_at_session_end_even_short_of_the_target():
    """The target was 355.10 and the price is 341 — it exits anyway."""
    s, _ = _in_position()
    intent = _tick(s, "PE", 341.00, 340.5, 341.5, CLOSE_MS)
    assert intent.kind == "submit_exit"
    assert s.trade.exit.reason == "session_end"


def test_before_session_end_the_policy_still_decides():
    s, _ = _in_position()
    assert _tick(s, "PE", 341.00, 340.5, 341.5, CLOSE_MS - 1000).kind == "none"


def test_session_end_wins_over_a_reachable_target():
    """Not a conflict in practice, but the ordering should be deliberate."""
    s, _ = _in_position()
    intent = _tick(s, "PE", 400.00, 399.5, 400.5, CLOSE_MS)
    assert intent.kind == "submit_exit"
    assert s.trade.exit.reason == "session_end"


def test_the_square_off_can_be_switched_off_for_research():
    s = _strategy(close_at_session_end=False)
    from .test_golden_trades import ScriptedBroker
    b = ScriptedBroker(entry_fill=340.10, exit_fill=356.00)
    intent = _tick(s, "CE", 491.15, 490.5, 491.6, OPEN_MS + 500)
    intent = _tick(s, "PE", 337.15, 336.6, 337.6, OPEN_MS + 900)
    while intent.kind not in ("none", "complete", "halt"):
        intent = b.run(s, intent)
    assert _tick(s, "PE", 341.00, 340.5, 341.5, CLOSE_MS).kind == "none"


def test_a_negative_entry_window_is_refused():
    with pytest.raises(ValueError, match="entry_window_seconds cannot be negative"):
        ATMPremiumImbalanceConfig(enabled=True, entry_window_seconds=-1).validate()
