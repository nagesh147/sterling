"""F-107 Risk-Per-Unit and F-108 Position Sizing for Adaptive Edge.

Canonical Master Specification v1.0 Provenance:
- Commit: 38f44f092fc4cd67291468ef5dbd5a3d8cfff0d1
- Section 31: Execution Cost
- Section 36: Initial Risk
- Section 62: Capital Objective
- Section 64: Strategy-Level Invariants

Formulas implemented:
- F-107: Nominal & Effective Risk-Per-Unit incorporating execution friction.
- F-108: Constrained Position Sizing & Effective Authorized Risk.

Governance:
Mathematical structures are frozen per Master Specification v1.0. All cost,
capital, and sizing parameters are managed via versioned ParameterMetadata.
Unvalidated or unversioned parameters fail closed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .contracts import RiskAuthorization, RiskState


class ParameterValidationStatus(str, Enum):
    UNRESOLVED = "unresolved"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ParameterEstimationMethod(str, Enum):
    CANONICAL_SPEC = "canonical_spec"
    WALK_FORWARD_ESTIMATE = "walk_forward_estimate"
    CALCULATED = "calculated"
    UNRESOLVED = "unresolved"


class ParameterGovernanceError(ValueError):
    """Raised when an formula computation encounters unvalidated parameter metadata."""


@dataclass(frozen=True)
class ParameterMetadata:
    """Governance metadata attached to every operational or learned parameter."""

    name: str
    value: float
    units: str
    version: str
    provenance: str
    estimation_method: ParameterEstimationMethod
    validation_status: ParameterValidationStatus
    applicable_instrument: str = "ALL"
    applicable_session: str = "ALL"
    applicable_regime: str = "ALL"

    def validate_or_raise(self) -> None:
        """Enforce strict parameter governance."""
        if not self.version or self.version.strip() == "":
            raise ParameterGovernanceError(f"Parameter '{self.name}' has empty version")
        if not self.provenance or self.provenance.strip() == "":
            raise ParameterGovernanceError(f"Parameter '{self.name}' has empty provenance")
        if self.validation_status is not ParameterValidationStatus.VALIDATED:
            raise ParameterGovernanceError(
                f"Parameter '{self.name}' has unvalidated status: {self.validation_status.value}"
            )
        if self.estimation_method is ParameterEstimationMethod.UNRESOLVED:
            raise ParameterGovernanceError(
                f"Parameter '{self.name}' has unresolved estimation method"
            )

    @property
    def is_valid(self) -> bool:
        try:
            self.validate_or_raise()
            return True
        except ParameterGovernanceError:
            return False


@dataclass(frozen=True)
class ExecutionCostParameters:
    """Execution cost components required by Section 31 for F-107."""

    spread_cost: ParameterMetadata
    expected_slippage: ParameterMetadata
    brokerage_per_unit: ParameterMetadata
    exchange_charges_per_unit: ParameterMetadata
    taxes_per_unit: ParameterMetadata
    latency_cost_per_unit: ParameterMetadata

    def validate_all(self) -> None:
        for param in (
            self.spread_cost,
            self.expected_slippage,
            self.brokerage_per_unit,
            self.exchange_charges_per_unit,
            self.taxes_per_unit,
            self.latency_cost_per_unit,
        ):
            param.validate_or_raise()
            if param.value < 0:
                raise ParameterGovernanceError(
                    f"Execution cost parameter '{param.name}' cannot be negative: {param.value}"
                )


@dataclass(frozen=True)
class SizingParameters:
    """Operational sizing limits required by Section 36 / 64 for F-108."""

    max_position_qty: ParameterMetadata
    max_capital_allocation: ParameterMetadata
    lot_size: ParameterMetadata

    def validate_all(self) -> None:
        for param in (self.max_position_qty, self.max_capital_allocation, self.lot_size):
            param.validate_or_raise()
            if param.value <= 0:
                raise ParameterGovernanceError(
                    f"Sizing parameter '{param.name}' must be strictly positive: {param.value}"
                )


@dataclass(frozen=True)
class RiskPerUnitAssessment:
    """Output assessment of F-107 Risk-Per-Unit calculation."""

    entry_price: float
    initial_stop: float
    nominal_risk_per_unit: float
    expected_execution_cost_per_unit: float
    effective_risk_per_unit: float
    valid: bool
    formula_id: str = "F-107"
    formula_version: str = "1.0"
    reason: Optional[str] = None


@dataclass(frozen=True)
class PositionSizingAssessment:
    """Output assessment of F-108 Position Sizing calculation."""

    target_quantity_unconstrained: int
    target_quantity_constrained: int
    final_quantity: int
    gross_authorized_risk: float
    effective_authorized_risk: float
    authorized_risk_budget: float
    valid: bool
    formula_id: str = "F-108"
    formula_version: str = "1.0"
    reason: Optional[str] = None


def calculate_risk_per_unit(
    entry_price: float,
    initial_stop: float,
    cost_params: ExecutionCostParameters,
    *,
    fail_closed: bool = True,
) -> RiskPerUnitAssessment:
    """Calculate F-107 Risk-Per-Unit and Effective Risk-Per-Unit.

    Formula (Master Spec v1.0 Sec 31, Sec 36):
      NominalRiskPerUnit = EntryPrice - InitialStop
      ExpectedExecutionCostPerUnit = sum(Spread + Slippage + Brokerage + ExchangeCharges + Taxes + Latency)
      EffectiveRiskPerUnit = NominalRiskPerUnit + ExpectedExecutionCostPerUnit
    """
    try:
        cost_params.validate_all()
    except ParameterGovernanceError as err:
        if fail_closed:
            raise
        return RiskPerUnitAssessment(
            entry_price=entry_price,
            initial_stop=initial_stop,
            nominal_risk_per_unit=0.0,
            expected_execution_cost_per_unit=0.0,
            effective_risk_per_unit=0.0,
            valid=False,
            reason=f"parameter_governance_failure: {err}",
        )

    if entry_price <= 0:
        if fail_closed:
            raise ValueError(f"Entry price must be strictly positive: {entry_price}")
        return RiskPerUnitAssessment(
            entry_price=entry_price,
            initial_stop=initial_stop,
            nominal_risk_per_unit=0.0,
            expected_execution_cost_per_unit=0.0,
            effective_risk_per_unit=0.0,
            valid=False,
            reason="invalid_entry_price",
        )

    if initial_stop <= 0:
        if fail_closed:
            raise ValueError(f"Initial stop must be strictly positive: {initial_stop}")
        return RiskPerUnitAssessment(
            entry_price=entry_price,
            initial_stop=initial_stop,
            nominal_risk_per_unit=0.0,
            expected_execution_cost_per_unit=0.0,
            effective_risk_per_unit=0.0,
            valid=False,
            reason="invalid_initial_stop",
        )

    nominal_risk = entry_price - initial_stop
    if nominal_risk <= 0:
        if fail_closed:
            raise ValueError(
                f"Initial stop ({initial_stop}) must be below entry price ({entry_price})"
            )
        return RiskPerUnitAssessment(
            entry_price=entry_price,
            initial_stop=initial_stop,
            nominal_risk_per_unit=nominal_risk,
            expected_execution_cost_per_unit=0.0,
            effective_risk_per_unit=0.0,
            valid=False,
            reason="non_positive_nominal_risk",
        )

    cost_per_unit = (
        cost_params.spread_cost.value
        + cost_params.expected_slippage.value
        + cost_params.brokerage_per_unit.value
        + cost_params.exchange_charges_per_unit.value
        + cost_params.taxes_per_unit.value
        + cost_params.latency_cost_per_unit.value
    )

    effective_risk = nominal_risk + cost_per_unit

    # Invariants assertion
    if effective_risk < nominal_risk or effective_risk <= 0:
        if fail_closed:
            raise ValueError("Effective risk invariant violation")
        return RiskPerUnitAssessment(
            entry_price=entry_price,
            initial_stop=initial_stop,
            nominal_risk_per_unit=nominal_risk,
            expected_execution_cost_per_unit=cost_per_unit,
            effective_risk_per_unit=effective_risk,
            valid=False,
            reason="effective_risk_invariant_violation",
        )

    return RiskPerUnitAssessment(
        entry_price=entry_price,
        initial_stop=initial_stop,
        nominal_risk_per_unit=nominal_risk,
        expected_execution_cost_per_unit=cost_per_unit,
        effective_risk_per_unit=effective_risk,
        valid=True,
        reason=None,
    )


def calculate_position_sizing(
    risk_auth: RiskAuthorization,
    risk_unit_assessment: RiskPerUnitAssessment,
    sizing_params: SizingParameters,
    *,
    fail_closed: bool = True,
) -> PositionSizingAssessment:
    """Calculate F-108 Position Sizing and Authorized Risk.

    Formula (Master Spec v1.0 Sec 36, Sec 62, Sec 64):
      Q_unconstrained = floor(MaxRisk / EffectiveRiskPerUnit)
      Q_capital_capped = floor(MaxCapitalAllocation / EntryPrice)
      Q_constrained = min(Q_unconstrained, MaxPositionQty, Q_capital_capped)
      Q_lots = floor(Q_constrained / LotSize) * LotSize
      GrossAuthorizedRisk = NominalRiskPerUnit * Q_lots
      EffectiveAuthorizedRisk = EffectiveRiskPerUnit * Q_lots
    """
    try:
        sizing_params.validate_all()
    except ParameterGovernanceError as err:
        if fail_closed:
            raise
        return PositionSizingAssessment(
            target_quantity_unconstrained=0,
            target_quantity_constrained=0,
            final_quantity=0,
            gross_authorized_risk=0.0,
            effective_authorized_risk=0.0,
            authorized_risk_budget=risk_auth.authorized_risk if risk_auth else 0.0,
            valid=False,
            reason=f"parameter_governance_failure: {err}",
        )

    if risk_auth is None or risk_auth.risk_state not in (RiskState.AUTHORIZED, RiskState.REDUCED):
        if fail_closed:
            raise ValueError(
                f"Risk authorization must be in AUTHORIZED or REDUCED state, got: {risk_auth.risk_state if risk_auth else None}"
            )
        return PositionSizingAssessment(
            target_quantity_unconstrained=0,
            target_quantity_constrained=0,
            final_quantity=0,
            gross_authorized_risk=0.0,
            effective_authorized_risk=0.0,
            authorized_risk_budget=risk_auth.authorized_risk if risk_auth else 0.0,
            valid=False,
            reason="unauthorized_risk_state",
        )

    if risk_auth.authorized_risk <= 0:
        return PositionSizingAssessment(
            target_quantity_unconstrained=0,
            target_quantity_constrained=0,
            final_quantity=0,
            gross_authorized_risk=0.0,
            effective_authorized_risk=0.0,
            authorized_risk_budget=risk_auth.authorized_risk,
            valid=True,
            reason="zero_risk_budget",
        )

    if not risk_unit_assessment.valid or risk_unit_assessment.effective_risk_per_unit <= 0:
        if fail_closed:
            raise ValueError("Invalid F-107 risk unit assessment passed to F-108 position sizing")
        return PositionSizingAssessment(
            target_quantity_unconstrained=0,
            target_quantity_constrained=0,
            final_quantity=0,
            gross_authorized_risk=0.0,
            effective_authorized_risk=0.0,
            authorized_risk_budget=risk_auth.authorized_risk,
            valid=False,
            reason="invalid_risk_unit_assessment",
        )

    effective_risk_per_unit = risk_unit_assessment.effective_risk_per_unit
    entry_price = risk_unit_assessment.entry_price

    # Unconstrained quantity: floor(MaxRisk / EffectiveRiskPerUnit)
    q_unconstrained = math.floor(risk_auth.authorized_risk / effective_risk_per_unit)
    if q_unconstrained < 0:
        q_unconstrained = 0

    max_pos_qty = int(sizing_params.max_position_qty.value)
    max_capital = sizing_params.max_capital_allocation.value
    lot_size = int(sizing_params.lot_size.value)

    q_capital_capped = math.floor(max_capital / entry_price) if entry_price > 0 else 0
    if q_capital_capped < 0:
        q_capital_capped = 0

    q_constrained = min(q_unconstrained, max_pos_qty, q_capital_capped)
    if q_constrained < 0:
        q_constrained = 0

    # Step size by lot_size
    if lot_size > 0:
        final_q = (q_constrained // lot_size) * lot_size
    else:
        final_q = q_constrained

    gross_risk = risk_unit_assessment.nominal_risk_per_unit * final_q
    effective_risk = effective_risk_per_unit * final_q

    # Invariants enforcement
    if effective_risk > risk_auth.authorized_risk + 1e-9:
        if fail_closed:
            raise ValueError(
                f"Effective risk ({effective_risk}) exceeds authorized risk budget ({risk_auth.authorized_risk})"
            )
        return PositionSizingAssessment(
            target_quantity_unconstrained=q_unconstrained,
            target_quantity_constrained=q_constrained,
            final_quantity=0,
            gross_authorized_risk=0.0,
            effective_authorized_risk=0.0,
            authorized_risk_budget=risk_auth.authorized_risk,
            valid=False,
            reason="effective_risk_exceeds_authorized_budget",
        )

    return PositionSizingAssessment(
        target_quantity_unconstrained=q_unconstrained,
        target_quantity_constrained=q_constrained,
        final_quantity=final_q,
        gross_authorized_risk=gross_risk,
        effective_authorized_risk=effective_risk,
        authorized_risk_budget=risk_auth.authorized_risk,
        valid=True,
        reason=None,
    )
