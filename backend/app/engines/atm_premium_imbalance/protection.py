"""Broker-side protection for an open position.

The source bot holds its position in process memory and exits when *it* sees the
target. If the process dies, the socket drops, or the box loses network, the
position simply sits there with nothing watching it. That is acceptable in a
recording and unacceptable with real money, so this module adds a protective
order that lives at the **exchange** and does not depend on us staying alive.

Three modes, because the safe thing and the faithful thing differ here:

* ``NONE``                 -- reproduce the observed bot exactly. Paper only.
* ``RESTING_TARGET_LIMIT`` -- park a SELL limit at the target the moment the
  entry fills. If we die, the exchange still takes the profit at the target.
* ``GTT``                  -- a broker Good-Till-Triggered order, for brokers
  that support a server-side trigger rather than a resting order.

A resting limit at the target is *not* the observed exit (the bot waits for a
trigger and then sells at ``best_bid - 0.50``, which can fill either side of the
target). So enabling protection deliberately changes the fill distribution, and
that is stated rather than hidden: see :func:`describe_divergence`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import ATMPremiumImbalanceConfig
from .models import OptionType, align_to_tick, q2

PROTECTION_MODES: frozenset[str] = frozenset({"NONE", "RESTING_TARGET_LIMIT", "GTT"})


class ProtectionState(str, Enum):
    ABSENT = "absent"
    PENDING = "pending"
    ACTIVE = "active"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    FILLED = "filled"
    FAILED = "failed"


@dataclass(frozen=True)
class ProtectionOrder:
    """The protective exit we want sitting at the exchange."""

    kind: str                     # RESTING_TARGET_LIMIT | GTT
    instrument_id: str
    option_type: OptionType
    side: str                     # always SELL for a long option
    quantity: int
    limit_price: float
    trigger_price: Optional[float] = None
    order_id: Optional[str] = None
    state: ProtectionState = ProtectionState.PENDING

    @property
    def is_live(self) -> bool:
        return self.state in (ProtectionState.PENDING, ProtectionState.ACTIVE)


def plan_protection(
    cfg: ATMPremiumImbalanceConfig,
    *,
    instrument_id: str,
    option_type: OptionType,
    quantity: int,
    entry_fill: float,
    target_price: float,
    tick_size: float = 0.05,
) -> Optional[ProtectionOrder]:
    """Build the protective order, or ``None`` when protection is off.

    The limit sits exactly at the target and is rounded *down* to the tick, so
    tick alignment can only make it fill more readily -- never leave it resting
    above the target where it might be skipped.
    """
    mode = cfg.protection_mode
    if mode == "NONE":
        return None
    if mode not in PROTECTION_MODES:
        raise ValueError(f"unknown protection_mode: {mode}")
    if entry_fill <= 0 or target_price <= 0:
        raise ValueError("protection requires a positive entry fill and target")
    if quantity <= 0:
        raise ValueError("protection requires a positive quantity")

    limit = align_to_tick(q2(target_price), tick_size, mode="down")
    if limit <= 0:
        raise ValueError("computed protection limit is not positive")

    trigger = None
    if mode == "GTT":
        # Trigger a shade below the limit so the order is live by the time the
        # market prints the target, rather than racing it.
        trigger = align_to_tick(q2(limit - max(tick_size, cfg.exit_buffer_points)), tick_size, mode="down")
        if trigger <= 0:
            trigger = limit

    return ProtectionOrder(
        kind=mode,
        instrument_id=instrument_id,
        option_type=option_type,
        side="SELL",
        quantity=quantity,
        limit_price=limit,
        trigger_price=trigger,
    )


def describe_divergence(cfg: ATMPremiumImbalanceConfig) -> str:
    """State plainly how protection departs from the observed behaviour."""
    if cfg.protection_mode == "NONE":
        return ("No broker-side protection. Reproduces the observed bot exactly: "
                "if this process dies while long, nothing exits the position.")
    return (
        f"protection_mode={cfg.protection_mode} parks a SELL at the target "
        f"({cfg.target_points:+g} points off the fill) at the exchange. The observed bot "
        f"instead waited for its own trigger and then sold at best_bid - "
        f"{cfg.exit_buffer_points:g}, which could fill either side of the target. "
        "Protected runs are therefore NOT byte-comparable to the recordings."
    )


def requires_cancel_before_exit(order: Optional[ProtectionOrder]) -> bool:
    """Whether our own exit must cancel the protective order first.

    It must. Leaving a live resting sell while sending another sell is how one
    long position becomes a short one.
    """
    return order is not None and order.is_live


def reconcile(order: Optional[ProtectionOrder], *, broker_says_filled: bool,
              broker_says_open: bool) -> ProtectionState:
    """Fold broker truth into the protective order's state.

    Disagreement resolves to ``FAILED`` rather than a guess: an unknown resting
    sell is a position of unknown sign.
    """
    if order is None:
        return ProtectionState.ABSENT
    if broker_says_filled and broker_says_open:
        return ProtectionState.FAILED
    if broker_says_filled:
        return ProtectionState.FILLED
    if broker_says_open:
        return ProtectionState.ACTIVE
    if order.state is ProtectionState.CANCEL_PENDING:
        return ProtectionState.CANCELLED
    return ProtectionState.FAILED
