"""A36 fill-derived position lifecycle primitives.

This module deliberately does not implement a stop, target, trailing rule,
or execution assumption. Position truth comes only from confirmed fills.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PositionLifecycleError(ValueError):
    """Raised when a position lifecycle invariant is violated."""


class PositionState(str, Enum):
    NO_POSITION = "NO_POSITION"
    OPENING = "OPENING"
    OPEN = "OPEN"
    REDUCING = "REDUCING"
    CLOSED = "CLOSED"


class ProtectionState(str, Enum):
    UNPROTECTED = "UNPROTECTED"
    PROTECTED = "PROTECTED"
    PROTECTION_PENDING = "PROTECTION_PENDING"
    PROTECTION_BREACH = "PROTECTION_BREACH"
    PROTECTION_INVALID = "PROTECTION_INVALID"


@dataclass(frozen=True)
class PositionLifecycle:
    position_id: str
    instrument_id: str
    state: PositionState
    protection_state: ProtectionState
    quantity: int

    def __post_init__(self) -> None:
        if not self.position_id.strip() or not self.instrument_id.strip():
            raise PositionLifecycleError("position and instrument identifiers are required")
        if self.quantity < 0:
            raise PositionLifecycleError("quantity cannot be negative")
        if self.state is PositionState.NO_POSITION and self.quantity != 0:
            raise PositionLifecycleError("NO_POSITION requires zero quantity")
        if self.state is PositionState.CLOSED and self.quantity != 0:
            raise PositionLifecycleError("CLOSED requires zero quantity")
        if self.quantity > 0 and self.state in {PositionState.NO_POSITION, PositionState.CLOSED}:
            raise PositionLifecycleError("non-zero quantity requires an active lifecycle state")


def initial_position(position_id: str, instrument_id: str) -> PositionLifecycle:
    return PositionLifecycle(
        position_id=position_id,
        instrument_id=instrument_id,
        state=PositionState.NO_POSITION,
        protection_state=ProtectionState.UNPROTECTED,
        quantity=0,
    )


def apply_confirmed_fill(
    position: PositionLifecycle,
    *,
    instrument_id: str,
    signed_quantity: int,
) -> PositionLifecycle:
    """Apply one confirmed fill to lifecycle quantity.

    The caller supplies only a confirmed fill. This function does not infer
    fills from orders, prices, triggers, or protection events.
    """
    if not instrument_id.strip() or instrument_id != position.instrument_id:
        raise PositionLifecycleError("fill instrument does not match position")
    if signed_quantity == 0:
        raise PositionLifecycleError("confirmed fill quantity must be non-zero")
    if position.state is PositionState.CLOSED:
        raise PositionLifecycleError("closed position cannot receive a normal fill")

    new_quantity = position.quantity + signed_quantity
    if new_quantity < 0:
        raise PositionLifecycleError("fill would make canonical quantity negative")
    if new_quantity == 0:
        return PositionLifecycle(position.position_id, position.instrument_id, PositionState.CLOSED, position.protection_state, 0)
    if position.quantity == 0:
        state = PositionState.OPENING
    elif abs(new_quantity) < abs(position.quantity):
        state = PositionState.REDUCING
    else:
        state = PositionState.OPEN
    return PositionLifecycle(position.position_id, position.instrument_id, state, position.protection_state, new_quantity)


def mark_protection_invalid(position: PositionLifecycle) -> PositionLifecycle:
    if position.quantity == 0:
        raise PositionLifecycleError("NO_POSITION cannot have position-specific protection invalidated")
    return PositionLifecycle(position.position_id, position.instrument_id, position.state, ProtectionState.PROTECTION_INVALID, position.quantity)
