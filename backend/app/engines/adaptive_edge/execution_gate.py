"""Final execution gate for Adaptive Edge.

The gate is intentionally independent from broker/execution adapters. Its only
job is to determine whether a strategy decision is authorized to cross into an
execution boundary.

The readiness module owns the canonical required-formula set so readiness and
execution cannot drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .formula_registry import FormulaStatus, get_formula
from .readiness import REQUIRED_STRATEGY_FORMULAS


class ExecutionGateStatus(str, Enum):
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExecutionGateDecision:
    status: ExecutionGateStatus
    required_formulas: tuple[str, ...]
    blocking_formulas: tuple[str, ...]
    reason: str | None = None

    @property
    def authorized(self) -> bool:
        return self.status is ExecutionGateStatus.AUTHORIZED


def evaluate_execution_gate(
    formula_ids: Iterable[str] = REQUIRED_STRATEGY_FORMULAS,
) -> ExecutionGateDecision:
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
            reason="required_strategy_formula_not_implemented",
        )

    return ExecutionGateDecision(
        status=ExecutionGateStatus.AUTHORIZED,
        required_formulas=required,
        blocking_formulas=(),
        reason=None,
    )


def require_execution_authorized(
    formula_ids: Iterable[str] = REQUIRED_STRATEGY_FORMULAS,
) -> ExecutionGateDecision:
    decision = evaluate_execution_gate(formula_ids)
    if not decision.authorized:
        raise ExecutionBlockedError(decision)
    return decision


class ExecutionBlockedError(RuntimeError):
    """Raised when execution crosses an unresolved strategy boundary."""

    def __init__(self, decision: ExecutionGateDecision) -> None:
        self.decision = decision
        super().__init__(
            "Adaptive Edge execution blocked: "
            + ", ".join(decision.blocking_formulas)
            + " require authoritative resolution before execution"
        )
