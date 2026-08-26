"""Implementation, registration, and promotion are three separate things.

strategy_v21.py implements F-101..F-114 as real code. The registry still holds
them LOCKED, because a formula becomes IMPLEMENTED there only after its
canonical specification has been recovered and tests attached — writing the
function is not what makes it authoritative. And even a fully IMPLEMENTED
registry would not make the engine executable, because promotion is a further
gate.

This file was written on 2026-08-12 asserting the registry already said
IMPLEMENTED at version 2.1.0. The 2026-08-18 reconciliation settled on LOCKED.
The invariant worth holding is that each step is separate, so no single edit can
walk the engine from "someone wrote a formula" to "it may risk money".
"""
import pytest

from app.engines.adaptive_edge import strategy_v21
from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula
from app.engines.adaptive_edge.promotion import CURRENT_STRATEGY_PROMOTION, PromotionStatus, require_promoted
from app.engines.adaptive_edge.readiness import assess_strategy_readiness

STRATEGY_FORMULA_IDS = tuple(f"F-{number:03d}" for number in range(101, 115))


def test_strategy_v21_supplies_an_implementation_for_every_strategy_formula():
    """The code exists — that is a fact about strategy_v21, not about the registry."""
    for number in range(101, 115):
        assert any(
            name.startswith(f"f{number}_") for name in dir(strategy_v21)
        ), f"strategy_v21 has no f{number}_* implementation"


def test_the_registry_has_not_accepted_those_implementations():
    for formula_id in STRATEGY_FORMULA_IDS:
        assert get_formula(formula_id).status is FormulaStatus.LOCKED


def test_implementation_does_not_imply_production_readiness():
    readiness = assess_strategy_readiness()
    assert readiness.unresolved_formula_ids == STRATEGY_FORMULA_IDS
    assert readiness.promotion_status is PromotionStatus.RESEARCH_ONLY
    assert readiness.executable is False
    assert readiness.reason == "required_strategy_formulas_unresolved"


def test_current_strategy_requires_explicit_promotion():
    assert CURRENT_STRATEGY_PROMOTION.strategy_version == "2.1.0-proposed"
    assert CURRENT_STRATEGY_PROMOTION.status is PromotionStatus.RESEARCH_ONLY
    with pytest.raises(RuntimeError, match="not production-promoted"):
        require_promoted("2.1.0-proposed")
