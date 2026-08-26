import pytest

from app.engines.adaptive_edge.position_lifecycle import (
    PositionLifecycleError,
    PositionState,
    ProtectionState,
    apply_confirmed_fill,
    initial_position,
    mark_protection_invalid,
)


def test_initial_position_has_no_position():
    p = initial_position("p1", "NIFTY")
    assert p.state is PositionState.NO_POSITION
    assert p.quantity == 0


def test_confirmed_fill_opens_position():
    p = apply_confirmed_fill(initial_position("p1", "NIFTY"), instrument_id="NIFTY", signed_quantity=10)
    assert p.state is PositionState.OPENING
    assert p.quantity == 10


def test_reducing_fill_does_not_imply_full_close():
    p = apply_confirmed_fill(initial_position("p1", "NIFTY"), instrument_id="NIFTY", signed_quantity=10)
    p = apply_confirmed_fill(p, instrument_id="NIFTY", signed_quantity=-4)
    assert p.state is PositionState.REDUCING
    assert p.quantity == 6


def test_only_fill_can_close_position():
    p = apply_confirmed_fill(initial_position("p1", "NIFTY"), instrument_id="NIFTY", signed_quantity=10)
    p = apply_confirmed_fill(p, instrument_id="NIFTY", signed_quantity=-10)
    assert p.state is PositionState.CLOSED
    assert p.quantity == 0


def test_mismatched_instrument_rejected():
    with pytest.raises(PositionLifecycleError):
        apply_confirmed_fill(initial_position("p1", "NIFTY"), instrument_id="BANKNIFTY", signed_quantity=1)


def test_protection_invalid_is_position_specific():
    p = apply_confirmed_fill(initial_position("p1", "NIFTY"), instrument_id="NIFTY", signed_quantity=1)
    p = mark_protection_invalid(p)
    assert p.protection_state is ProtectionState.PROTECTION_INVALID


def test_no_position_cannot_have_protection_invalidated():
    with pytest.raises(PositionLifecycleError):
        mark_protection_invalid(initial_position("p1", "NIFTY"))


def test_closed_position_cannot_receive_normal_fill():
    p = apply_confirmed_fill(initial_position("p1", "NIFTY"), instrument_id="NIFTY", signed_quantity=1)
    p = apply_confirmed_fill(p, instrument_id="NIFTY", signed_quantity=-1)
    with pytest.raises(PositionLifecycleError):
        apply_confirmed_fill(p, instrument_id="NIFTY", signed_quantity=1)
