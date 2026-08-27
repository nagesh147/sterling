"""Order-price arithmetic for Adaptive Edge.

Small and per-engine by convention here, rather than shared: the rounding
direction on an exit is a strategy decision, not a utility, and one engine
changing it must not silently change another's fills.
"""
from __future__ import annotations

from math import floor

#: NSE option tick. Every option premium is a multiple of this, and an order at
#: a price that is not lands as a rejection rather than a fill.
DEFAULT_TICK = 0.05


def align_to_tick(price: float, tick: float = DEFAULT_TICK) -> float:
    """Round a price down onto the exchange tick grid.

    Down, not nearest: on an entry this pays no more than intended, and a price
    off the grid is rejected outright.
    """
    if tick <= 0:
        return round(float(price), 2)
    return round(floor(float(price) / tick) * tick, 2)


def exit_order_price(ltp: float, tick: float = DEFAULT_TICK, *, slip_ticks: int = 2) -> float:
    """A limit price for an exit that should actually fill.

    Priced *through* the last trade by a couple of ticks. A limit exactly at the
    last price is the order that sits unfilled while the position keeps moving
    against you — which is the opposite of what an exit is for. Never below one
    tick, because a zero or negative limit is a rejection.
    """
    if ltp <= 0:
        return tick
    through = float(ltp) - max(0, int(slip_ticks)) * tick
    return max(tick, align_to_tick(through, tick))


def stop_from_entry(entry: float, stop_percent: float, tick: float = DEFAULT_TICK) -> float:
    """The protective stop for a long option, as a percentage of premium.

    Options are bought here, never written, so the stop is always below entry.
    Floored at one tick: a stop of zero is not a stop, it is a position with no
    downside boundary at all.
    """
    raw = float(entry) * (1.0 - max(0.0, min(100.0, float(stop_percent))) / 100.0)
    return max(tick, align_to_tick(raw, tick))
