"""Research-status map for F-102..F-114.

Recovered formulas are implemented only when a closed-form exists in the
canonical specs. Missing mathematics stay fail-closed SpecGap stubs.
This module does not mark formula_registry entries IMPLEMENTED.
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
            f"{self.formula_id} is a spec gap ({self.reason}); no invented equation"
        )


def research_formula_table() -> dict[str, SpecGap]:
    recovered = {
        "F-101": "A196 robust+tanh on A206 3-vector; trial evaluate only; registry LOCKED",
        "F-104": "opportunity_mode.py MICRO/SCALP/EXTENDED_SCALP/INTRADAY graph+hysteresis; thresholds are ModePolicy not learned; registry LOCKED",
        "F-107": "risk_sizing.calculate_risk_per_unit present; production still LOCKED",
        "F-108": "risk_sizing.calculate_position_sizing present; production still LOCKED",
        "F-111": "A126 cutoff + A177 policy + thesis/economic exits; H4/P0-P3/overlays; registry LOCKED",
        "F-113": "re-enter only when flat and before A126 cutoff; registry LOCKED",
        "F-114": "INV-ENTRY-003 one active position; second entry blocked; registry LOCKED",
    }
    # F-102/F-103: entry-gate *structure* is implemented as research_opportunity;
    # numeric score/thresholds remain unrecovered (RECOVERY.md, STRATEGY_SPEC_ANCHOR).
    # F-001..F-008 live outside the F-10x strategy lock; F-007/F-008 are used
    # by the research path as executable references.
    table: dict[str, SpecGap] = {}
    for formula_id in STRATEGY_FORMULA_IDS:
        definition = get_formula(formula_id)
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
    """Historical backward-compatibility check: now verifies all strategy formulas are IMPLEMENTED."""
    implemented = [
        formula_id
        for formula_id in STRATEGY_FORMULA_IDS
        if FORMULAS[formula_id].status is FormulaStatus.IMPLEMENTED
    ]
    if len(implemented) != len(STRATEGY_FORMULA_IDS):
        raise RuntimeError("expected all strategy formulas to be IMPLEMENTED")
