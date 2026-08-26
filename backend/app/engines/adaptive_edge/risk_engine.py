"""Canonical risk authorization and sizing primitives.

Risk is independent from predictive confidence and DynamicMode. Authorization
is immutable by construction: state transitions create new objects instead of
mutating an existing authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .canonical_math import maximum_accepted_risk, position_size, risk_per_unit


@dataclass(frozen=True)
class RiskAuthorization:
    authorization_id: str
    opportunity_id: str
    authorization_time: datetime
    authorized_risk: float
    risk_per_unit: float
    risk_policy_version: str
    status: str
    expiry: datetime | None = None

    def resized_quantity(self, lot_size: int) -> int:
        return position_size(self.authorized_risk, self.risk_per_unit, lot_size)


def authorize(
    *,
    authorization_id: str,
    opportunity_id: str,
    authorization_time: datetime,
    authorized_risk: float,
    entry_price: float,
    initial_stop: float,
    point_value: float,
    effective_execution_cost_per_unit: float,
    risk_policy_version: str,
    expiry: datetime | None = None,
) -> RiskAuthorization:
    if authorized_risk < 0:
        raise ValueError("authorized risk cannot be negative")
    unit_risk = risk_per_unit(
        entry_price,
        initial_stop,
        point_value,
        effective_execution_cost_per_unit,
    )
    return RiskAuthorization(
        authorization_id=authorization_id,
        opportunity_id=opportunity_id,
        authorization_time=authorization_time,
        authorized_risk=authorized_risk,
        risk_per_unit=unit_risk,
        risk_policy_version=risk_policy_version,
        status="AUTHORIZED" if authorized_risk > 0 else "DENIED",
        expiry=expiry,
    )


def tighten(previous: RiskAuthorization, proposed_risk: float) -> RiskAuthorization:
    """Create a new authorization that can only preserve or reduce risk."""
    accepted = maximum_accepted_risk(previous.authorized_risk, proposed_risk)
    return RiskAuthorization(
        authorization_id=previous.authorization_id,
        opportunity_id=previous.opportunity_id,
        authorization_time=previous.authorization_time,
        authorized_risk=accepted,
        risk_per_unit=previous.risk_per_unit,
        risk_policy_version=previous.risk_policy_version,
        status=previous.status,
        expiry=previous.expiry,
    )
