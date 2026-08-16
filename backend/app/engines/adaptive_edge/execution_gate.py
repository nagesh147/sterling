"""Final execution gate for Adaptive Edge.

The gate is intentionally independent from broker/execution adapters. Its only
job is to determine whether a strategy decision is authorized to cross into an
execution boundary.

Adaptive Edge remains non-executable while any required strategy-specific
formula is unresolved. This module makes that invariant executable and
machine-testable instead of relying on callers to remember the policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .formula_registry import FormulaStatus, get_formula


REQUIRED_STRATEGY_FORMULAS: tuple[str, ...] = tuple(
    f"F-{number:03d}" for number in range(101, 115)
)


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
    """Evaluate the final strategy execution gate.

    Every required formula must be explicitly IMPLEMENTED. Unknown formula IDs
    are treated as blocking rather than ignored. This guarantees fail-closed
    behavior when the registry and caller disagree.
    """
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
    """Return the authorized decision or raise a deterministic gate error."""
    decision = evaluate_execution_gate(formula_ids)
    if not decision.authorized:
        raise ExecutionBlockedError(decision)
    return decision


class ExecutionBlockedError(RuntimeError):
    """Raised when strategy execution crosses an unresolved formula boundary."""

    def __init__(self, decision: ExecutionGateDecision) -> None:
        self.decision = decision
        super().__init__(
            "Adaptive Edge execution blocked: "
            + ", ".join(decision.blocking_formulas)
            + " require authoritative resolution before execution"
        )


@dataclass(frozen=True)
class FrictionExpectancyDecision:
    authorized: bool
    expected_gain_inr: float
    estimated_friction_inr: float
    friction_ratio: float
    reason: str | None = None


def evaluate_friction_expectancy_gate(
    *,
    entry_price: float,
    target_price: float,
    lot_size: int,
    estimated_friction_inr: float = 60.0,
    min_friction_multiplier: float = 4.0,
) -> FrictionExpectancyDecision:
    """Validate that expected trade gain exceeds minimum friction multiplier threshold.

    Guards against retail micro-churn where STT and transaction taxes consume alpha.
    """
    points_gain = max(0.0, abs(target_price - entry_price))
    expected_gain = points_gain * max(1, lot_size)
    min_required = estimated_friction_inr * min_friction_multiplier
    if expected_gain < min_required:
        return FrictionExpectancyDecision(
            authorized=False,
            expected_gain_inr=round(expected_gain, 2),
            estimated_friction_inr=round(estimated_friction_inr, 2),
            friction_ratio=round(expected_gain / max(1.0, estimated_friction_inr), 2),
            reason=f"expected_gain_below_friction_threshold ({expected_gain:.2f} < {min_required:.2f})",
        )
    return FrictionExpectancyDecision(
        authorized=True,
        expected_gain_inr=round(expected_gain, 2),
        estimated_friction_inr=round(estimated_friction_inr, 2),
        friction_ratio=round(expected_gain / max(1.0, estimated_friction_inr), 2),
        reason=None,
    )
