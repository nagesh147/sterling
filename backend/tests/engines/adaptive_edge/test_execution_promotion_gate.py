"""Execution needs a resolved formula set AND a promoted strategy.

Written on 2026-08-12 against a design where F-101..F-114 were registered
IMPLEMENTED and promotion was the only thing left blocking execution. The
governance model that replaced it on 2026-08-17/18 keeps the formulas LOCKED, so
the formula gate blocks first and promotion is a second, independent gate. The
property being tested is unchanged — nothing reaches a broker — but which gate
refuses, and why, is now asserted for each gate separately.
"""
import pytest

from app.engines.adaptive_edge.execution_gate import (
    REQUIRED_STRATEGY_FORMULAS,
    ExecutionBlockedError,
    ExecutionGateStatus,
    evaluate_execution_gate,
    evaluate_strategy_promotion_gate,
    require_execution_authorized,
)
from app.engines.adaptive_edge.promotion import CURRENT_STRATEGY_PROMOTION, PromotionStatus


def test_strategy_formulas_are_not_resolved_so_the_formula_gate_blocks():
    decision = evaluate_execution_gate()
    assert decision.status is ExecutionGateStatus.BLOCKED
    assert decision.blocking_formulas == REQUIRED_STRATEGY_FORMULAS
    assert decision.reason == "required_strategy_formula_not_implemented"


def test_promotion_is_a_separate_gate_and_also_blocks():
    """Independent of the formulas: this strategy is not cleared to trade."""
    decision = evaluate_strategy_promotion_gate()
    assert decision.status is ExecutionGateStatus.BLOCKED
    assert decision.reason == "strategy_promotion_required"
    assert CURRENT_STRATEGY_PROMOTION.status is PromotionStatus.RESEARCH_ONLY


def test_resolving_every_formula_would_still_not_be_enough():
    """The two gates are independent, so neither alone can make the engine live.

    This is the guarantee the promotion gate exists for: finishing the
    mathematics must never be the same act as authorizing real money.
    """
    assert evaluate_execution_gate(("F-004",)).authorized is True
    assert evaluate_strategy_promotion_gate().authorized is False


def test_execution_authorization_fails_closed():
    with pytest.raises(ExecutionBlockedError, match="required_strategy_formula_not_implemented"):
        require_execution_authorized()
