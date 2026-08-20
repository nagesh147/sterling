"""Research-status map for Adaptive Edge strategy formulas.

The V1.0 master strategy source has been recovered. Entries therefore
represent source recovery/canonicalization state, not production authority.
This module never marks formula_registry entries IMPLEMENTED.
"""
from __future__ import annotations

from dataclasses import dataclass

from .formula_registry import FORMULAS, FormulaStatus, get_formula

STRATEGY_FORMULA_IDS: tuple[str, ...] = tuple(
    f"F-{number:03d}" for number in range(101, 115)
)


@dataclass(frozen=True)
class SpecGap:
    formula_id: str
    name: str
    status: str
    reason: str

    def evaluate(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError(
            f"{self.formula_id} is not production-resolved ({self.reason})"
        )


def research_formula_table() -> dict[str, SpecGap]:
    recovered = {
        "F-101": "V1.0 feature/state architecture recovered; canonical inputs and calibration remain under review",
        "F-102": "V1.0 probability/regime architecture recovered; model/calibration semantics remain under review",
        "F-103": "V1.0 candidate eligibility and NO_TRADE boundary recovered; complete contract remains under review",
        "F-104": "V1.0 horizon distribution and management classifications recovered; learned transition parameters remain unfrozen",
        "F-105": "V1.0 target/stop competition and conservative EV recovered; empirical distributions and parameters require validation",
        "F-106": "V1.0 option candidate economics recovered; candidate inputs and validation remain under review",
        "F-107": "V1.0 RiskPerUnit/GrossRisk/effective-risk relationship recovered only partially; semantic reconciliation required",
        "F-108": "V1.0 quantity equation recovered; implementation exists; promotion and parameter validation remain pending",
        "F-109": "V1.0 option selection recovered as max ExpectedNetEV subject to liquidity/slippage/risk/data-quality constraints",
        "F-110": "V1.0 BUY_CE/BUY_PE mandatory gate recovered; implementation exists; promotion remains pending",
        "F-111": "V1.0 hard/continuation/reversal/session exit semantics recovered; implementation exists; promotion remains pending",
        "F-112": "V1.0 monotonic protection and learned giveback/continuation parameters recovered; parameters remain unfrozen",
        "F-113": "V1.0 post-exit learning and re-entry boundary recovered; exact re-entry admission contract remains under review",
        "F-114": "V1.0 decision includes PositionState/CapitalState, but a unique multi-position risk aggregation equation remains unresolved",
    }
    table: dict[str, SpecGap] = {}
    for formula_id in STRATEGY_FORMULA_IDS:
        definition = get_formula(formula_id)
        # A formula with no recovered closed-form is a SPEC_GAP, not an
        # implicitly-recovered one: the unguarded `recovered[formula_id]` this
        # replaced raised KeyError instead of reporting the gap.
        if definition.status is FormulaStatus.IMPLEMENTED:
            reason = "registry IMPLEMENTED"
            status = "IMPLEMENTED"
        elif formula_id in recovered:
            reason = recovered[formula_id]
            status = "RESEARCH_CODE_PRESENT_REGISTRY_LOCKED"
        else:
            reason = "no recovered closed-form; fail closed"
            status = "SPEC_GAP"
        table[formula_id] = SpecGap(
            formula_id=formula_id,
            name=definition.name,
            status=status,
            reason=reason,
        )
    return table


def assert_production_strategy_locked() -> None:
    """Enforce that every strategy-specific formula remains LOCKED."""
    unlocked = [
        formula_id
        for formula_id in STRATEGY_FORMULA_IDS
        if FORMULAS[formula_id].status is not FormulaStatus.LOCKED
    ]
    if unlocked:
        raise RuntimeError(
            "production strategy formulas must remain LOCKED: " + ", ".join(unlocked)
        )
