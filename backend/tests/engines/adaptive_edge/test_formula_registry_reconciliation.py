from __future__ import annotations

import pytest

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula, require_implemented


def test_strategy_formula_registry_matches_canonical_contract_names() -> None:
    expected = {
        "F-101": "Feature/state construction and normalization",
        "F-102": "Probability/regime state",
        "F-103": "Candidate eligibility / NO_TRADE boundary",
        "F-104": "Adaptive horizon distribution",
        "F-105": "Target/stop competition and conservative EV",
        "F-106": "Option candidate economics",
        "F-107": "Effective risk semantics",
        "F-108": "Position sizing",
        "F-109": "Option selection by validated ExpectedNetEV subject to constraints",
        "F-110": "BUY_CE / BUY_PE mandatory entry gate",
        "F-111": "Position-management exit state machine",
        "F-112": "Monotonic dynamic protection / profit floor",
        "F-113": "Post-exit / re-entry boundary",
        "F-114": "Final decision interaction with PositionState and CapitalState",
    }
    for formula_id, name in expected.items():
        definition = get_formula(formula_id)
        assert definition.name == name
        assert definition.status is FormulaStatus.LOCKED


def test_locked_strategy_formula_cannot_execute() -> None:
    with pytest.raises(RuntimeError, match="not executable"):
        require_implemented("F-114")
