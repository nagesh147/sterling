"""Final execution gate for Adaptive Edge.

Formula implementation and strategy promotion are independent gates. The gate
fails closed when formulas are incomplete OR when the current strategy version
has not passed explicit promotion approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .formula_registry import FormulaStatus, get_formula
from .promotion import CURRENT_STRATEGY_PROMOTION, PromotionStatus
from .readiness import REQUIRED_STRATEGY_FORMULAS


class ExecutionGateStatus(str, Enum):
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionGateDecision:
    status: ExecutionGateStatus
    required_formulas: tuple[str, ...]
    blocking_formulas: tuple[str, ...]
    promotion_status: PromotionStatus
    reason: str | None = None

    @property
    def authorized(self) -> bool:
        return self.status is ExecutionGateStatus.AUTHORIZED


def evaluate_execution_gate(formula_ids: Iterable[str] = REQUIRED_STRATEGY_FORMULAS) -> ExecutionGateDecision:
    """Evaluate the final strategy execution gate fail-closed."""
    required = tuple(formula_ids)
    blocking: list[str] = []
    for formula_id in required:
        try:
            definition = get_formula(formula_id)
        except KeyError:
            blocking.append(formula_id)
            continue
        if definition.status is not FormulaStatus.IMPLEMENTED:
            blocking.append(formula_id)

    if blocking:
        return ExecutionGateDecision(
            status=ExecutionGateStatus.BLOCKED,
            required_formulas=required,
            blocking_formulas=tuple(blocking),
            promotion_status=CURRENT_STRATEGY_PROMOTION.status,
            reason="required_strategy_formula_not_implemented",
        )

    if CURRENT_STRATEGY_PROMOTION.status is not PromotionStatus.APPROVED:
        return ExecutionGateDecision(
            status=ExecutionGateStatus.BLOCKED,
            required_formulas=required,
            blocking_formulas=(),
            promotion_status=CURRENT_STRATEGY_PROMOTION.status,
            reason="strategy_promotion_required",
        )

    return ExecutionGateDecision(
        status=ExecutionGateStatus.AUTHORIZED,
        required_formulas=required,
        blocking_formulas=(),
        promotion_status=CURRENT_STRATEGY_PROMOTION.status,
        reason=None,
    )


def require_execution_authorized(formula_ids: Iterable[str] = REQUIRED_STRATEGY_FORMULAS) -> ExecutionGateDecision:
    decision = evaluate_execution_gate(formula_ids)
    if not decision.authorized:
        raise ExecutionBlockedError(decision)
    return decision


class ExecutionBlockedError(RuntimeError):
    """Raised when execution crosses an unresolved or unpromoted strategy boundary."""

    def __init__(self, decision: ExecutionGateDecision) -> None:
        self.decision = decision
        details = decision.reason or "execution not authorized"
        if decision.blocking_formulas:
            details += ": " + ", ".join(decision.blocking_formulas)
        super().__init__("Adaptive Edge execution blocked: " + details)
