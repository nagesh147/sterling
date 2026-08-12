"""Fail-closed readiness boundary for the Adaptive Edge strategy.

This module answers only whether the strategy has enough source-resolved
mathematics to be executable. It does not invent or evaluate strategy
formulas.
"""
from __future__ import annotations

from dataclasses import dataclass

from .formula_registry import FormulaStatus, get_formula

REQUIRED_STRATEGY_FORMULAS: tuple[str, ...] = tuple(
    f"F-{number:03d}" for number in range(101, 115)
)


@dataclass(frozen=True)
class StrategyReadiness:
    executable: bool
    required_formula_ids: tuple[str, ...]
    unresolved_formula_ids: tuple[str, ...]
    reason: str | None


def assess_strategy_readiness() -> StrategyReadiness:
    unresolved: list[str] = []
    for formula_id in REQUIRED_STRATEGY_FORMULAS:
        try:
            definition = get_formula(formula_id)
        except KeyError:
            unresolved.append(formula_id)
            continue
        if definition.status is not FormulaStatus.IMPLEMENTED:
            unresolved.append(formula_id)

    return StrategyReadiness(
        executable=not unresolved,
        required_formula_ids=REQUIRED_STRATEGY_FORMULAS,
        unresolved_formula_ids=tuple(unresolved),
        reason=None if not unresolved else "required_strategy_formulas_unresolved",
    )


def require_strategy_ready() -> StrategyReadiness:
    readiness = assess_strategy_readiness()
    if not readiness.executable:
        raise RuntimeError(
            "Adaptive Edge strategy is not executable: "
            + ", ".join(readiness.unresolved_formula_ids)
        )
    return readiness
