"""Realistic stop-fill price for the position monitor.

The background monitor polls on an interval. When it finally sees a stop
breach, the live price has already run PAST the stop, and the old code booked
the exit at that poll-time price (`current_spot`) — charging the entire
interval's drift as slippage. On large positions that turned breakeven stops
into big losses (e.g. a stop AT entry filling 2pts beyond → full-size loss).

A real stop order fills ~at the stop ± a few bps. `realistic_stop_fill` caps
the booked slippage at `max_slip_bps`, using the smaller of the actual
overshoot and the cap, direction-aware.
"""
from __future__ import annotations

from app.engines.directional.trailing_stop import realistic_stop_fill


def test_short_caps_overshoot_slippage():
    # short stop at 2027.7 (breakeven), price drifted to 2029.75 by next poll
    fill = realistic_stop_fill(stop=2027.7, spot=2029.75, direction_sign=-1, max_slip_bps=5.0)
    cap = 2027.7 * 5 / 10_000  # ~1.01
    assert fill == 2027.7 + cap            # capped, not the full 2.05 overshoot
    assert fill < 2029.75


def test_long_caps_overshoot_slippage():
    fill = realistic_stop_fill(stop=2018.11, spot=2015.0, direction_sign=1, max_slip_bps=5.0)
    cap = 2018.11 * 5 / 10_000
    assert fill == 2018.11 - cap
    assert fill > 2015.0


def test_uses_actual_overshoot_when_smaller_than_cap():
    # short: only 0.3 past the stop, well under the 5bps cap → book the 0.3
    fill = realistic_stop_fill(stop=100.0, spot=100.3, direction_sign=-1, max_slip_bps=50.0)
    assert fill == 100.3                    # cap = 0.5 > 0.3, so actual used


def test_no_overshoot_fills_at_stop():
    assert realistic_stop_fill(stop=100.0, spot=100.0, direction_sign=-1) == 100.0
    # price on the favourable side of the stop → still fills at stop, no credit
    assert realistic_stop_fill(stop=100.0, spot=99.0, direction_sign=-1) == 100.0


def test_breakeven_stop_loss_is_only_slippage():
    """The key regression: a breakeven stop must cost ~slippage, not the
    full overshoot the monitor happened to observe."""
    entry = 2027.7
    contracts = 437
    old_loss = (2029.75 - entry) * contracts          # what the bug booked
    fill = realistic_stop_fill(stop=entry, spot=2029.75, direction_sign=-1, max_slip_bps=5.0)
    new_loss = (fill - entry) * contracts
    assert new_loss < old_loss
    assert new_loss <= entry * 5 / 10_000 * contracts + 1e-6
