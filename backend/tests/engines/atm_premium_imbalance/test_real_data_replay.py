"""Findings from replaying the recordings against real Kite minute bars.

The bar values below were fetched from Kite historical for the actual traded
contracts and are frozen here, so the conclusions survive the session expiring
and the contracts being delisted.

The headline finding is that the source strategy prices its entry off a **stale
tick**. Our engine reproduces its arithmetic exactly; fed the exchange's real
opening price it produces a different, better order price.
"""
import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, InstrumentRef, price_entry, select_atm_strike,
)

# --- real SENSEX index 09:15 IST bar opens (Kite token 265) ------------------
INDEX_OPEN = {
    "2026-08-20": 77468.45,
    "2026-08-21": 77701.07,
}

# --- real 09:15 IST bars for SENSEX 77700, expiry 2026-08-27 -----------------
#     CE token 212046597, PE token 212614405
PE_0821_OPEN_BAR = {"open": 356.70, "high": 356.70, "low": 318.00, "close": 334.25}
CE_0821_OPEN_BAR = {"open": 500.00, "high": 545.60, "low": 450.00, "close": 452.55}
#     the same PE in the *previous* session's closing minutes
PE_0820_LATE_RANGE = (373.90, 379.90)

LADDER = [77300.0, 77400.0, 77500.0, 77600.0, 77700.0, 77800.0]


def inst(strike, option_type="PE"):
    return InstrumentRef(instrument_id="I", tradingsymbol="S", option_type=option_type,
                         strike=strike, expiry="2026-08-27", lot_size=20,
                         tick_size=0.05, upper_circuit=3000.0)


def cfg():
    return ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10
    ).validate()


# ------------------------------------------------------- strike selection

@pytest.mark.parametrize(
    "session,printed_strike",
    [("2026-08-20", 77500.0), ("2026-08-21", 77700.0)],
)
def test_atm_rule_reproduces_the_printed_strike_from_the_real_index(session, printed_strike):
    """Both recordings' strikes fall out of the real 09:15 index open."""
    assert select_atm_strike(INDEX_OPEN[session], LADDER) == printed_strike


def test_the_2026_08_20_strike_was_not_a_close_call_the_other_way():
    o = INDEX_OPEN["2026-08-20"]
    assert abs(77500 - o) < abs(77400 - o)      # 31.55 vs 68.45


# --------------------------------------------------------- leg selection

def test_the_put_really_was_the_cheaper_leg_on_2026_08_21():
    """The recording bought the PE; the real opens agree."""
    assert PE_0821_OPEN_BAR["open"] < CE_0821_OPEN_BAR["open"]      # 356.70 < 500.00


# ------------------------------------------------- the stale-tick finding

def test_our_rule_reproduces_the_bots_order_price_from_the_bots_own_input():
    """Given 379.0, we produce 416.9 -- exactly what the bot printed.

    So the rule is right; only the input differs.
    """
    priced = price_entry(cfg(), inst(77700.0), best_ask=None, first_tick_price=379.00)
    assert priced.limit_price == 416.90


def test_the_bots_first_tick_is_impossible_at_the_real_open():
    """379.0 lies outside the 09:15 bar entirely."""
    lo, hi = PE_0821_OPEN_BAR["low"], PE_0821_OPEN_BAR["high"]
    assert not (lo <= 379.00 <= hi)             # 318.00 .. 356.70
    # ...but sits inside the PREVIOUS session's closing range
    assert PE_0820_LATE_RANGE[0] <= 379.00 <= PE_0820_LATE_RANGE[1]


def test_the_real_open_yields_a_materially_different_order_price():
    """Fed the exchange's open, the same rule prices 24.5 points lower.

    356.70 x 1.10 = 392.37 -> 392.4, against the bot's 416.9. The stale tick was
    6.3% high and the x1.10 rule amplified it.
    """
    priced = price_entry(cfg(), inst(77700.0), best_ask=None,
                         first_tick_price=PE_0821_OPEN_BAR["open"])
    assert priced.limit_price == 392.40
    assert round(416.90 - 392.40, 2) == 24.50


def test_the_bots_limit_was_far_through_the_real_open():
    """416.9 against a 356.70 open is 16.9% through the market.

    At that distance the limit is not a price opinion, it is 'take whatever the
    book has' -- which is how the fill landed at 340.10, *below* the open.
    """
    open_px = PE_0821_OPEN_BAR["open"]
    through = (416.90 - open_px) / open_px
    assert round(through * 100, 1) == 16.9
    fill = 340.10
    assert fill < open_px                                  # paid less than the open
    assert PE_0821_OPEN_BAR["low"] <= fill <= PE_0821_OPEN_BAR["high"]


def test_the_target_was_reachable_in_the_minute_after_entry():
    """fill 340.10 + 15 = 355.10, and the 09:16 bar high was 360.00."""
    target = round(340.10 + 15.0, 2)
    assert target == 355.10
    assert 360.00 >= target       # 09:16 high (real bar)
