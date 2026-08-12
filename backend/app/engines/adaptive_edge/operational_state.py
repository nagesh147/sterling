"""A56 operational-state interaction primitives.

Operational state constrains trading permissions explicitly. It does not
invent strategy-specific recovery, liquidation, or risk policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OperationalStateError(ValueError):
    """Raised when an A56 state/permission invariant is violated."""


class OperationalState(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    BLOCK_NEW = "block_new"
    HALTED = "halted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TradingPermissions:
    allow_signal_generation: bool
    allow_new_entries: bool
    allow_existing_position_management: bool
    allow_exit_submission: bool


@dataclass(frozen=True)
class OperationalTradingState:
    state_id: str
    operational_state: OperationalState
    permissions: TradingPermissions
    observation_id: str
    policy_id: str
    policy_version: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.state_id, "state_id"),
            (self.observation_id, "observation_id"),
            (self.policy_id, "policy_id"),
            (self.policy_version, "policy_version"),
        ):
            if not value.strip():
                raise OperationalStateError(f"{name} must not be empty")

        if self.operational_state in {OperationalState.BLOCK_NEW, OperationalState.HALTED} and self.permissions.allow_new_entries:
            raise OperationalStateError("blocked or halted state cannot allow new entries")

        if self.operational_state == OperationalState.HALTED and self.permissions.allow_signal_generation:
            raise OperationalStateError("halted state cannot allow signal generation")


def validate_operational_trading_state(state: OperationalTradingState) -> OperationalTradingState:
    """Return a validated state without inferring any missing policy."""
    return state
