"""Causal V2.1 target construction.

This module implements only the registered A26-ND market-outcome label family.
It never fabricates missing future observations and never reads execution/P&L.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Sequence


class LabelStatus(str, Enum):
    PENDING = "PENDING"
    MATURE = "MATURE"
    CENSORED = "CENSORED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class TargetSpec:
    horizon_bars: int
    neutral_threshold: float
    version: str

    def __post_init__(self) -> None:
        if self.horizon_bars <= 0:
            raise ValueError("horizon_bars must be positive")
        if self.neutral_threshold < 0:
            raise ValueError("neutral_threshold must be non-negative")
        if not self.version.strip():
            raise ValueError("version must not be empty")


@dataclass(frozen=True)
class MarketObservation:
    timestamp: datetime
    availability_time: datetime
    price: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.availability_time.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.price <= 0:
            raise ValueError("reference price must be positive")


@dataclass(frozen=True)
class OutcomeLabel:
    decision_time: datetime
    outcome_start_time: datetime
    outcome_end_time: datetime | None
    label: str | None
    status: LabelStatus
    label_definition_version: str
    label_maturity_time: datetime | None
    return_value: float | None
    reason: str | None = None


def build_label(
    observations: Sequence[MarketObservation],
    *,
    decision_index: int,
    spec: TargetSpec,
) -> OutcomeLabel:
    """Build one causal label from a time-ordered reference-price series.

    The decision observation itself must already be available at its decision time.
    The terminal observation is future outcome information and is used only for
    label construction after it becomes available.
    """
    if not observations:
        raise ValueError("observations must not be empty")
    if not 0 <= decision_index < len(observations):
        raise IndexError("decision_index out of range")

    decision = observations[decision_index]
    if decision.availability_time > decision.timestamp:
        return OutcomeLabel(
            decision.timestamp,
            decision.timestamp,
            None,
            None,
            LabelStatus.INVALID,
            spec.version,
            None,
            None,
            "decision observation was unavailable at decision time",
        )

    terminal_index = decision_index + spec.horizon_bars
    if terminal_index >= len(observations):
        return OutcomeLabel(
            decision.timestamp,
            decision.timestamp,
            None,
            None,
            LabelStatus.PENDING,
            spec.version,
            None,
            None,
            "terminal outcome observation is not yet present",
        )

    terminal = observations[terminal_index]
    if terminal.availability_time > terminal.timestamp:
        return OutcomeLabel(
            decision.timestamp,
            decision.timestamp,
            terminal.timestamp,
            None,
            LabelStatus.CENSORED,
            spec.version,
            terminal.availability_time,
            None,
            "terminal observation is not available at its represented outcome time",
        )

    if terminal.timestamp <= decision.timestamp:
        return OutcomeLabel(
            decision.timestamp,
            decision.timestamp,
            terminal.timestamp,
            None,
            LabelStatus.INVALID,
            spec.version,
            terminal.availability_time,
            None,
            "terminal observation does not occur after decision time",
        )

    future_return = terminal.price / decision.price - 1.0
    if future_return > spec.neutral_threshold:
        label = "UP"
    elif future_return < -spec.neutral_threshold:
        label = "DOWN"
    else:
        label = "NEUTRAL"

    return OutcomeLabel(
        decision.timestamp,
        decision.timestamp,
        terminal.timestamp,
        label,
        LabelStatus.MATURE,
        spec.version,
        terminal.availability_time,
        future_return,
    )


def preregistered_specs() -> tuple[TargetSpec, ...]:
    """Return the exact A26-ND research grid; no adaptive candidate generation."""
    horizons = (5, 10, 15, 30)
    thresholds = (0.0, 0.0010, 0.0025, 0.0050)
    return tuple(
        TargetSpec(
            horizon_bars=horizon,
            neutral_threshold=threshold,
            version=f"A26-ND-2.1-H{horizon}-T{threshold:g}",
        )
        for horizon in horizons
        for threshold in thresholds
    )
