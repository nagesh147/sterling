"""Fail-closed readiness boundary for the Adaptive Edge strategy.

Formula implementation and production promotion are separate gates. A complete
implemented strategy can therefore be researched without becoming executable.
"""
from __future__ import annotations

from dataclasses import dataclass

from .formula_registry import FormulaStatus, get_formula
from .promotion import CURRENT_STRATEGY_PROMOTION, PromotionStatus

REQUIRED_STRATEGY_FORMULAS: tuple[str, ...] = tuple(
    f"F-{number:03d}" for number in range(101, 115)
)


@dataclass(frozen=True)
class StrategyReadiness:
    executable: bool
    required_formula_ids: tuple[str, ...]
    unresolved_formula_ids: tuple[str, ...]
    promotion_status: PromotionStatus
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

    if unresolved:
        reason = "required_strategy_formulas_unresolved"
    elif CURRENT_STRATEGY_PROMOTION.status is not PromotionStatus.APPROVED:
        reason = "strategy_promotion_required"
    else:
        reason = None

    return StrategyReadiness(
        executable=not unresolved and reason is None,
        required_formula_ids=REQUIRED_STRATEGY_FORMULAS,
        unresolved_formula_ids=tuple(unresolved),
        promotion_status=CURRENT_STRATEGY_PROMOTION.status,
        reason=reason,
    )


def require_strategy_ready() -> StrategyReadiness:
    readiness = assess_strategy_readiness()
    if not readiness.executable:
        details = readiness.reason or "unknown"
        if readiness.unresolved_formula_ids:
            details += ": " + ", ".join(readiness.unresolved_formula_ids)
        raise RuntimeError("Adaptive Edge strategy is not executable: " + details)
    return readiness
