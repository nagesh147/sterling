"""Price arithmetic for Adaptive Edge orders.

Small functions, but they decide the price an order goes out at and where the
stop sits, and they are otherwise only exercised incidentally through arm() and
the exit path. Every case below is checked at more than one price magnitude:
an off-by-a-tick that is invisible at 120 is obvious at 3.

The exchange rejects a price that is not a multiple of the tick, so "roughly
right" is not a category here — an unaligned price is a rejected order.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.execution import (
    DEFAULT_TICK,
    align_to_tick,
    exit_order_price,
    stop_from_entry,
)


def _on_grid(price: float, tick: float = DEFAULT_TICK) -> bool:
    return abs(round(price / tick) - (price / tick)) < 1e-9


# ------------------------------------------------------------ align_to_tick

@pytest.mark.parametrize("raw,expected", [
    (120.37, 120.35),
    (120.00, 120.00),
    (3.03, 3.00),
    (0.07, 0.05),
    (24_999.99, 24_999.95),
])
def test_align_rounds_down_onto_the_grid(raw, expected):
    """Down, not nearest: on an entry this pays no more than intended."""
    assert align_to_tick(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [0.05, 3.4, 87.65, 1234.55])
def test_an_already_aligned_price_is_unchanged(raw):
    assert align_to_tick(raw) == pytest.approx(raw)


@pytest.mark.parametrize("raw", [0.06, 1.99, 120.37, 9_876.54])
def test_every_aligned_price_sits_on_the_tick_grid(raw):
    assert _on_grid(align_to_tick(raw))


def test_a_zero_tick_does_not_divide_by_zero():
    assert align_to_tick(120.374, 0.0) == pytest.approx(120.37)


# -------------------------------------------------------- exit_order_price

@pytest.mark.parametrize("ltp", [3.0, 47.5, 120.0, 5_400.0])
def test_the_exit_limit_is_priced_through_the_last_trade(ltp):
    """A limit exactly at the last price is the order that sits unfilled while
    the position keeps moving against you, which is the opposite of an exit."""
    price = exit_order_price(ltp)
    assert price < ltp
    assert _on_grid(price)


def test_the_slip_is_the_configured_number_of_ticks():
    assert exit_order_price(120.0, slip_ticks=2) == pytest.approx(119.90)
    assert exit_order_price(120.0, slip_ticks=4) == pytest.approx(119.80)
    assert exit_order_price(120.0, slip_ticks=0) == pytest.approx(120.00)


@pytest.mark.parametrize("ltp", [0.05, 0.10, 0.0, -5.0])
def test_the_exit_limit_never_goes_to_zero_or_below(ltp):
    """A zero or negative limit is a rejection, so a position that has collapsed
    to near nothing must still produce a sendable exit."""
    price = exit_order_price(ltp)
    assert price >= DEFAULT_TICK


def test_a_negative_slip_is_treated_as_none_rather_than_priced_upward():
    """Pricing an exit *above* the market would be a limit that never fills."""
    assert exit_order_price(120.0, slip_ticks=-5) == pytest.approx(120.00)


# --------------------------------------------------------- stop_from_entry

@pytest.mark.parametrize("entry,percent,expected", [
    (100.0, 30.0, 70.0),
    (120.0, 30.0, 84.0),
    (3.00, 30.0, 2.10),
    (5_400.0, 10.0, 4_860.0),
])
def test_the_stop_is_a_percentage_below_entry(entry, percent, expected):
    assert stop_from_entry(entry, percent) == pytest.approx(expected)


@pytest.mark.parametrize("entry", [0.10, 7.35, 120.0, 9_999.95])
def test_the_stop_is_always_below_entry_and_on_the_grid(entry):
    """Options are bought here, never written, so the stop is always below."""
    stop = stop_from_entry(entry, 30.0)
    assert stop < entry
    assert _on_grid(stop)


def test_a_hundred_percent_stop_still_leaves_a_real_price():
    """A stop of zero is not a stop, it is a position with no downside boundary."""
    assert stop_from_entry(120.0, 100.0) == pytest.approx(DEFAULT_TICK)


def test_a_stop_percent_outside_the_range_is_clamped_not_inverted():
    """A negative percentage would put the stop ABOVE entry, which is an
    immediate exit at best and an inverted position at worst."""
    assert stop_from_entry(100.0, -20.0) == pytest.approx(100.0)
    assert stop_from_entry(100.0, 250.0) == pytest.approx(DEFAULT_TICK)


def test_stop_and_exit_price_agree_at_the_same_magnitude():
    """The two together decide what a stop-out actually fills at, so they must
    stay consistent: the exit limit for a stopped position sits just below it."""
    entry = 120.0
    stop = stop_from_entry(entry, 30.0)
    fill = exit_order_price(stop)
    assert fill < stop
    assert stop - fill == pytest.approx(2 * DEFAULT_TICK)
