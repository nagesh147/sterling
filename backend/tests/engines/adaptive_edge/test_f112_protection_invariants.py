from __future__ import annotations

import pytest

from app.engines.adaptive_edge.protection import ProtectionEngine, ProtectionPolicy


def test_f112_long_protection_tightens_with_new_extreme() -> None:
    engine = ProtectionEngine(
        ProtectionPolicy(
            label="test",
            protective_stop_points=10,
            trail_points=5,
            profit_lock_activation_points=20,
            profit_lock_offset_points=8,
        ),
        side="BUY",
        entry_price=100,
    )
    first = engine.update(120)
    second = engine.update(130)
    assert second.extreme >= first.extreme
    assert second.trail_price >= first.trail_price


def test_f112_profit_lock_activates_only_after_threshold() -> None:
    engine = ProtectionEngine(
        ProtectionPolicy(
            label="test",
            protective_stop_points=10,
            profit_lock_activation_points=20,
            profit_lock_offset_points=5,
        ),
        side="BUY",
        entry_price=100,
    )
    assert engine.update(119).lock_active is False
    assert engine.update(120).lock_active is True


def test_f112_invalid_policy_distance_fails_closed() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        ProtectionPolicy(label="bad", protective_stop_points=0)
