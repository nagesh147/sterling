"""Signal, quote-cache and selection unit tests.

Every numeric expectation traces to a row in
docs/strategy/atm-premium-imbalance/A231_FORENSIC_EVIDENCE_MATRIX.md.
"""
from datetime import date

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig,
    InstrumentRef,
    LegQuote,
    OptionPairRef,
    PremiumQuoteCache,
    evaluate,
    format_difference_line,
    resolve_pair,
    select_atm_strike,
    select_expiry,
)


def leg(option_type, strike=77600.0, expiry="2026-07-30", token="1"):
    return InstrumentRef(
        instrument_id=f"BSE_FO|{token}",
        tradingsymbol=f"SENSEX{int(strike)}{option_type}",
        option_type=option_type,
        strike=strike,
        expiry=expiry,
        lot_size=20,
        tick_size=0.05,
        upper_circuit=1745.45,
    )


@pytest.fixture
def pair():
    return OptionPairRef(
        underlying="SENSEX", expiry="2026-07-30", strike=77600.0,
        ce=leg("CE", token="1141595"), pe=leg("PE", token="1145203"),
    )


def q(instrument_id, ltp, *, bid=None, ask=None, ts=1000, recv=1000, seq=1):
    return LegQuote(
        instrument_id=instrument_id, ltp=ltp, bid=bid, ask=ask,
        exchange_ts_ms=ts, received_ts_ms=recv, sequence=seq,
    )


# --------------------------------------------------------------- difference

@pytest.mark.parametrize(
    "ce,pe,expected",
    [
        (106.80, 245.15, 138.35),   # A231 golden lines, V17
        (103.80, 246.40, 142.60),
        (138.10, 199.30, 61.20),
        (149.10, 192.60, 43.50),
        (167.50, 214.85, 47.35),    # V17 entry block
        (482.05, 620.00, 137.95),   # V04
        (126.90, 168.25, 41.35),    # V1 exit block
        # 2026-08-21 -- the first recording with the CALL dearer. The bot still
        # printed a positive 154.00, which is what proves the value is absolute.
        (491.15, 337.15, 154.00),
        (489.90, 335.05, 154.85),
    ],
)
def test_difference_is_the_absolute_gap(pair, ce, pe, expected):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, ce))
    cache.on_option_tick(q(pair.pe.instrument_id, pe))
    view = cache.view("COMPATIBILITY", 1000)
    assert view is not None
    assert view.difference == pytest.approx(expected, abs=1e-9)


def test_difference_line_matches_observed_format(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 141.00))
    cache.on_option_tick(q(pair.pe.instrument_id, 196.95))
    view = cache.view("COMPATIBILITY", 1000)
    assert format_difference_line(view) == "CE : 141.00 | PE : 196.95 | Difference : 55.95"


def test_difference_line_stays_positive_when_the_call_is_dearer(pair):
    """Verbatim from the 2026-08-21 recording."""
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 491.15))
    cache.on_option_tick(q(pair.pe.instrument_id, 337.15))
    view = cache.view("COMPATIBILITY", 1000)
    assert format_difference_line(view) == "CE : 491.15 | PE : 337.15 | Difference : 154.00"


def test_put_side_entry_is_taken_when_the_call_is_dearer(pair):
    """2026-08-21: CE 491.15 > PE 337.15 -> the put is bought.

    The first observed put-side entry; the Upstox notification in that recording
    confirms a fill at Rs. 340.10, i.e. against the ~337 put, not the ~491 call.
    """
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 491.15))
    cache.on_option_tick(q(pair.pe.instrument_id, 337.15))
    sig = evaluate(cache.view("COMPATIBILITY", 1000), ATMPremiumImbalanceConfig())
    assert (sig.action, sig.option_type) == ("BUY_PE", "PE")
    assert sig.difference == 154.00


# ------------------------------------------------------- independent caching

def test_legs_update_independently(pair):
    """V17: 106.80/245.15 -> 103.80/246.40 (both) -> 103.70/246.40 (CE only)
    -> 103.70/249.15 (PE only). A231/Q3."""
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 106.80, seq=1))
    cache.on_option_tick(q(pair.pe.instrument_id, 245.15, seq=1))
    assert cache.view("COMPATIBILITY", 1000).difference == pytest.approx(138.35)

    cache.on_option_tick(q(pair.ce.instrument_id, 103.70, seq=2))
    # PE untouched -> difference recomputed from the *cached* PE
    assert cache.view("COMPATIBILITY", 1000).difference == pytest.approx(141.45)

    cache.on_option_tick(q(pair.pe.instrument_id, 249.15, seq=2))
    assert cache.view("COMPATIBILITY", 1000).difference == pytest.approx(145.45)
    assert cache.update_counts == (2, 2)


def test_foreign_instrument_is_ignored(pair):
    cache = PremiumQuoteCache(pair)
    assert cache.on_option_tick(q("BSE_FO|999999", 10.0)) is None
    assert cache.view("COMPATIBILITY", 1000) is None


def test_out_of_order_sequence_is_dropped(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 100.0, seq=5))
    cache.on_option_tick(q(pair.ce.instrument_id, 90.0, seq=3))
    assert cache.ce.ltp == 100.0


def test_no_view_until_both_legs_present(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 100.0))
    assert cache.view("COMPATIBILITY", 1000) is None
    assert not cache.both_legs_present()


def test_first_option_tick_is_recorded_once(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.pe.instrument_id, 214.85))
    cache.on_option_tick(q(pair.ce.instrument_id, 167.50))
    kind, first = cache.first_option_tick
    assert (kind, first.ltp) == ("PE", 214.85)


# ------------------------------------------------------------------- modes

def test_executable_view_uses_asks_and_never_falls_back(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 167.50, bid=167.0, ask=168.0))
    cache.on_option_tick(q(pair.pe.instrument_id, 214.85))       # no ask
    assert cache.view("EXECUTABLE", 1000) is None                 # not an LTP fallback
    cache.on_option_tick(q(pair.pe.instrument_id, 214.85, bid=214.0, ask=215.5, seq=2))
    view = cache.view("EXECUTABLE", 1000)
    assert (view.ce_price, view.pe_price) == (168.0, 215.5)


def test_synchronized_view_respects_skew_window(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 100.0, ts=1_000))
    cache.on_option_tick(q(pair.pe.instrument_id, 200.0, ts=9_000))
    assert cache.view("SYNCHRONIZED", 9_000, max_skew_ms=1_000) is None
    cache.on_option_tick(q(pair.pe.instrument_id, 205.0, ts=1_400, seq=2))
    view = cache.view("SYNCHRONIZED", 9_000, max_skew_ms=1_000)
    assert view is not None and view.skew_ms == 400


def test_compatibility_is_not_silently_replaced(pair):
    """COMPATIBILITY must report cached LTPs even when asks disagree."""
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 167.50, ask=180.0))
    cache.on_option_tick(q(pair.pe.instrument_id, 214.85, ask=220.0))
    view = cache.view("COMPATIBILITY", 1000)
    assert (view.ce_price, view.pe_price) == (167.50, 214.85)
    assert view.mode == "COMPATIBILITY"


# ------------------------------------------------------------------ signal

@pytest.mark.parametrize(
    "ce,pe,action,leg_type",
    [(167.50, 214.85, "BUY_CE", "CE"), (250.0, 100.0, "BUY_PE", "PE")],
)
def test_cheaper_leg_is_bought(pair, ce, pe, action, leg_type):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, ce))
    cache.on_option_tick(q(pair.pe.instrument_id, pe))
    sig = evaluate(cache.view("COMPATIBILITY", 1000), ATMPremiumImbalanceConfig())
    assert (sig.action, sig.option_type) == (action, leg_type)


def test_equal_premiums_is_no_trade(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 150.0))
    cache.on_option_tick(q(pair.pe.instrument_id, 150.0))
    sig = evaluate(cache.view("COMPATIBILITY", 1000), ATMPremiumImbalanceConfig())
    assert (sig.action, sig.reason) == ("NO_TRADE", "equal_premiums")


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"session_open": False}, "session_closed"),
        ({"risk_authorized": False}, "risk_not_authorized"),
        ({"flat": False}, "position_open"),
        ({"trades_taken": 1}, "session_trade_limit_reached"),
    ],
)
def test_liveness_gates_reject_but_never_invert(pair, kwargs, reason):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 100.0))
    cache.on_option_tick(q(pair.pe.instrument_id, 200.0))
    sig = evaluate(cache.view("COMPATIBILITY", 1000), ATMPremiumImbalanceConfig(), **kwargs)
    assert (sig.action, sig.reason) == ("NO_TRADE", reason)


def test_stale_quote_blocks_entry(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 100.0, recv=0))
    cache.on_option_tick(q(pair.pe.instrument_id, 200.0, recv=0))
    cfg = ATMPremiumImbalanceConfig(max_quote_age_ms=500)
    assert evaluate(cache.view("COMPATIBILITY", 5_000), cfg).reason == "stale_quote"


def test_missing_view_is_no_trade_not_a_crash():
    sig = evaluate(None, ATMPremiumImbalanceConfig())
    assert (sig.action, sig.reason) == ("NO_TRADE", "no_quote_pair")


def test_minimum_difference_gate_is_off_by_default(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(q(pair.ce.instrument_id, 167.50))
    cache.on_option_tick(q(pair.pe.instrument_id, 168.00))   # 0.50 gap
    assert evaluate(cache.view("COMPATIBILITY", 1000), ATMPremiumImbalanceConfig()).action == "BUY_CE"
    cfg = ATMPremiumImbalanceConfig(minimum_difference=5.0)
    assert evaluate(cache.view("COMPATIBILITY", 1000), cfg).reason == "below_minimum_difference"


# --------------------------------------------------------------- selection

def test_atm_is_nearest_listed_strike():
    """V17: SENSEX 77638.86 -> 77600 (38.86 away) not 77700 (61.14). A231/M5."""
    assert select_atm_strike(77638.86, [77400, 77500, 77600, 77700, 77800]) == 77600


def test_atm_tie_breaks_to_lower_strike_deterministically():
    assert select_atm_strike(77650.0, [77600, 77700]) == 77600
    assert select_atm_strike(77650.0, [77700, 77600]) == 77600


def test_atm_uses_listed_strikes_not_an_assumed_step():
    assert select_atm_strike(77638.86, [77000, 77500, 78000]) == 77500


def test_same_day_expiry_is_strict():
    listed = ["2026-07-30", "2026-08-06"]
    assert select_expiry(listed, policy="SAME_DAY", today=date(2026, 7, 30)) == "2026-07-30"
    with pytest.raises(ValueError, match="no contract expires today"):
        select_expiry(listed, policy="SAME_DAY", today=date(2026, 7, 29))


def test_nearest_and_next_expiry():
    listed = ["2026-07-30", "2026-08-06", "2026-08-13"]
    assert select_expiry(listed, policy="NEAREST", today=date(2026, 7, 30)) == "2026-07-30"
    assert select_expiry(listed, policy="NEXT", today=date(2026, 7, 30)) == "2026-08-06"


def test_resolve_pair_requires_both_legs_at_the_strike():
    contracts = [
        leg("CE", 77600.0, token="1141595"),
        leg("PE", 77600.0, token="1145203"),
        leg("CE", 77700.0, token="2"),        # CE only -> not tradable
    ]
    resolved = resolve_pair(
        underlying="SENSEX", underlying_ltp=77690.0, contracts=contracts, expiry="2026-07-30"
    )
    assert resolved.strike == 77600.0          # 77700 skipped: no PE listed
    assert resolved.ce.instrument_id == "BSE_FO|1141595"
    assert resolved.pe.instrument_id == "BSE_FO|1145203"
