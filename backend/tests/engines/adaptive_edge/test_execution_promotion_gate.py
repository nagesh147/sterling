import pytest

from app.engines.adaptive_edge.execution_gate import ExecutionGateStatus, ExecutionBlockedError, evaluate_execution_gate, require_execution_authorized
from app.engines.adaptive_edge.promotion import PromotionStatus


def test_all_implemented_formulas_still_require_promotion():
    decision = evaluate_execution_gate()
    assert decision.status is ExecutionGateStatus.BLOCKED
    assert decision.blocking_formulas == ()
    assert decision.promotion_status is PromotionStatus.RESEARCH_ONLY
    assert decision.reason == "strategy_promotion_required"


def test_execution_authorization_fails_closed_before_promotion():
    with pytest.raises(ExecutionBlockedError, match="strategy_promotion_required"):
        require_execution_authorized()
