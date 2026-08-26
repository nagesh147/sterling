from __future__ import annotations

from app.engines.adaptive_edge.f112_protection_envelope import F112ProtectionEnvelope
from app.engines.adaptive_edge.protection import ProtectionPolicy


def test_f112_long_effective_stop_never_decreases():
    envelope = F112ProtectionEnvelope(
        ProtectionPolicy("test", protective_stop_points=5, trail_points=2,
                         profit_lock_activation_points=4, profit_lock_offset_points=1),
        side="BUY", entry_price=100,
    )
    stops = [envelope.update(mark)[1].effective_stop for mark in (100, 104, 108, 106, 110, 105)]
    assert all(a is not None and b is not None and b >= a for a, b in zip(stops, stops[1:]))


def test_f112_short_effective_stop_never_increases():
    envelope = F112ProtectionEnvelope(
        ProtectionPolicy("test", protective_stop_points=5, trail_points=2,
                         profit_lock_activation_points=4, profit_lock_offset_points=1),
        side="SELL", entry_price=100,
    )
    stops = [envelope.update(mark)[1].effective_stop for mark in (100, 96, 92, 94, 90, 95)]
    assert all(a is not None and b is not None and b <= a for a, b in zip(stops, stops[1:]))


def test_f112_profit_lock_activates_only_after_threshold():
    envelope = F112ProtectionEnvelope(
        ProtectionPolicy("test", protective_stop_points=5, trail_points=2,
                         profit_lock_activation_points=4, profit_lock_offset_points=1),
        side="BUY", entry_price=100,
    )
    assert envelope.update(103)[1].lock_active is False
    assert envelope.update(104)[1].lock_active is True
