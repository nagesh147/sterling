import pytest

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula
from app.engines.adaptive_edge.promotion import CURRENT_STRATEGY_PROMOTION, PromotionStatus, require_promoted
from app.engines.adaptive_edge.readiness import assess_strategy_readiness


def test_all_v21_strategy_formulas_are_implemented():
    for number in range(101, 115):
        definition = get_formula(f"F-{number:03d}")
        assert definition.version == "2.1.0"
        assert definition.status is FormulaStatus.IMPLEMENTED
        assert definition.owner == "strategy_v21"


def test_implementation_does_not_imply_production_readiness():
    readiness = assess_strategy_readiness()
    assert readiness.unresolved_formula_ids == ()
    assert readiness.promotion_status is PromotionStatus.RESEARCH_ONLY
    assert readiness.executable is False
    assert readiness.reason == "strategy_promotion_required"


def test_current_strategy_requires_explicit_promotion():
    assert CURRENT_STRATEGY_PROMOTION.strategy_version == "2.1.0-proposed"
    with pytest.raises(RuntimeError, match="not production-promoted"):
        require_promoted("2.1.0-proposed")
