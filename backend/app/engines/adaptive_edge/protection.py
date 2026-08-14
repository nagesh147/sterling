"""A177 protection authorities: stop, trail, profit-lock.

Numeric distances are caller-supplied policy, not recovered F-112.
Does not unlock formula_registry. Does not invent a default stop.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtectionPolicy:
    """Explicit distances in price points. Not a production freeze."""

    label: str
    protective_stop_points: float | None = None
    trail_points: float | None = None
    profit_lock_activation_points: float | None = None
    profit_lock_offset_points: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "protective_stop_points",
            "trail_points",
            "profit_lock_activation_points",
            "profit_lock_offset_points",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when supplied")


@dataclass(frozen=True)
class ProtectionDecision:
    authority: str | None
    hit: bool
    stop_price: float | None
    trail_price: float | None
    lock_price: float | None
    extreme: float
    lock_active: bool
    reason: str


class ProtectionEngine:
    """Stateful A177 trail/lock. Later marks may tighten, never loosen."""

    def __init__(self, policy: ProtectionPolicy, *, side: str, entry_price: float) -> None:
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        self.policy = policy
        self.side = side
        self.entry_price = float(entry_price)
        self.extreme = float(entry_price)
        self.lock_active = False

    def update(self, mark: float) -> ProtectionDecision:
        price = float(mark)
        if self.side == "BUY":
            self.extreme = max(self.extreme, price)
            favorable = self.extreme - self.entry_price
        else:
            self.extreme = min(self.extreme, price)
            favorable = self.entry_price - self.extreme

        stop = None
        if self.policy.protective_stop_points is not None:
            delta = self.policy.protective_stop_points
            stop = (
                self.entry_price - delta
                if self.side == "BUY"
                else self.entry_price + delta
            )

        trail = None
        if self.policy.trail_points is not None:
            delta = self.policy.trail_points
            trail = self.extreme - delta if self.side == "BUY" else self.extreme + delta

        if (
            self.policy.profit_lock_activation_points is not None
            and favorable >= self.policy.profit_lock_activation_points
        ):
            self.lock_active = True

        lock = None
        if self.lock_active and self.policy.profit_lock_offset_points is not None:
            delta = self.policy.profit_lock_offset_points
            lock = self.extreme - delta if self.side == "BUY" else self.extreme + delta

        hit_stop = stop is not None and (
            price <= stop if self.side == "BUY" else price >= stop
        )
        hit_trail = trail is not None and (
            price <= trail if self.side == "BUY" else price >= trail
        )
        hit_lock = lock is not None and (
            price <= lock if self.side == "BUY" else price >= lock
        )

        if hit_stop:
            authority, reason = "PROTECTIVE_STOP", "protective_stop_hit"
        elif hit_lock:
            authority, reason = "PROFIT_LOCK", "profit_lock_hit"
        elif hit_trail:
            authority, reason = "TRAILING_PROTECTION", "trailing_hit"
        else:
            authority, reason = None, "hold"
        return ProtectionDecision(
            authority=authority,
            hit=authority is not None,
            stop_price=stop,
            trail_price=trail,
            lock_price=lock,
            extreme=self.extreme,
            lock_active=self.lock_active,
            reason=reason,
        )
