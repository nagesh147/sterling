"""A37 source-faithful accounting boundary records.

These records preserve accounting lineage without inventing instrument,
fee, multiplier, valuation, currency-conversion, or risk formulas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class AccountingBoundaryError(ValueError):
    """Raised when accounting-boundary provenance or identity is invalid."""


def _required(value: str, name: str) -> None:
    if not value.strip():
        raise AccountingBoundaryError(f"{name} must not be empty")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None:
        raise AccountingBoundaryError(f"{name} must be timezone-aware")


@dataclass(frozen=True)
class CashEffect:
    effect_id: str
    source_fill_id: str
    amount: float
    currency: str
    occurred_at: datetime
    policy_version: str

    def __post_init__(self) -> None:
        _required(self.effect_id, "effect_id")
        _required(self.source_fill_id, "source_fill_id")
        _required(self.currency, "currency")
        _required(self.policy_version, "policy_version")
        _aware(self.occurred_at, "occurred_at")


@dataclass(frozen=True)
class ExecutionCost:
    cost_id: str
    source_fill_id: str
    component: str
    amount: float
    currency: str
    occurred_at: datetime
    source: str
    policy_version: str

    def __post_init__(self) -> None:
        for value, name in ((self.cost_id, "cost_id"), (self.source_fill_id, "source_fill_id"), (self.component, "component"), (self.currency, "currency"), (self.source, "source"), (self.policy_version, "policy_version")):
            _required(value, name)
        _aware(self.occurred_at, "occurred_at")


@dataclass(frozen=True)
class ValuationObservation:
    instrument_id: str
    price_type: str
    value: float
    source: str
    observation_time: datetime
    availability_time: datetime
    freshness_seconds: float
    valuation_policy_version: str

    def __post_init__(self) -> None:
        for value, name in ((self.instrument_id, "instrument_id"), (self.price_type, "price_type"), (self.source, "source"), (self.valuation_policy_version, "valuation_policy_version")):
            _required(value, name)
        _aware(self.observation_time, "observation_time")
        _aware(self.availability_time, "availability_time")
        if self.availability_time < self.observation_time:
            raise AccountingBoundaryError("availability_time cannot precede observation_time")
        if self.freshness_seconds < 0:
            raise AccountingBoundaryError("freshness_seconds cannot be negative")


@dataclass(frozen=True)
class RiskReconciliationBoundary:
    reconciliation_id: str
    authorization_id: str
    as_of: datetime
    authorized_risk_reference: str
    actual_state_reference: str
    status: str

    def __post_init__(self) -> None:
        for value, name in ((self.reconciliation_id, "reconciliation_id"), (self.authorization_id, "authorization_id"), (self.authorized_risk_reference, "authorized_risk_reference"), (self.actual_state_reference, "actual_state_reference"), (self.status, "status")):
            _required(value, name)
        _aware(self.as_of, "as_of")


def net_economic_result(gross_result: float, explicitly_defined_costs: tuple[ExecutionCost, ...]) -> float:
    """A37 structural relationship; callers must supply explicitly defined costs."""
    return gross_result - sum(cost.amount for cost in explicitly_defined_costs)
