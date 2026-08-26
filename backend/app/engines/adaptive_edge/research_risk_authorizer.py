"""Research-only adapter for the F-107/F-108 risk boundary.

This adapter consumes an already-issued RiskAuthorization. It cannot create,
raise, or mutate authorization and it cannot submit execution.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import RiskAuthorization
from .risk_sizing import (
    ExecutionCostParameters,
    PositionSizingAssessment,
    RiskPerUnitAssessment,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


@dataclass(frozen=True)
class ResearchRiskResult:
    risk_per_unit: RiskPerUnitAssessment
    sizing: PositionSizingAssessment


class ResearchRiskAuthorizer:
    """Adapt canonical F-107/F-108 calculations without granting risk."""

    def assess(
        self,
        authorization: RiskAuthorization,
        *,
        entry_price: float,
        initial_stop: float,
        cost_parameters: ExecutionCostParameters,
        sizing_parameters: SizingParameters,
    ) -> ResearchRiskResult:
        risk_per_unit = calculate_risk_per_unit(
            entry_price,
            initial_stop,
            cost_parameters,
            fail_closed=True,
        )
        sizing = calculate_position_sizing(
            authorization,
            risk_per_unit,
            sizing_parameters,
            fail_closed=True,
        )
        return ResearchRiskResult(risk_per_unit=risk_per_unit, sizing=sizing)
