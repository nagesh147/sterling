from __future__ import annotations

import pytest

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula, require_implemented


def test_strategy_formula_registry_matches_recovered_contract_names() -> None:
    expected = {
        "F-101": "Feature normalization",
        "F-102": "Probability / prediction state",
        "F-103": "Opportunity eligibility",
        "F-104": "Adaptive horizon distribution",
        "F-105": "Target/stop competition and conservative EV",
        "F-106": "Option candidate economic selection",
        "F-107": "Effective risk per unit",
        "F-108": "Position sizing",
        "F-109": "Option moneyness / listed-contract selection",
        "F-110": "Canonical order intent",
        "F-111": "Canonical execution event",
        "F-112": "Dynamic protection",
        "F-113": "Lifecycle termination",
        "F-114": "Final portfolio interaction",
    }
    for formula_id, name in expected.items():
        definition = get_formula(formula_id)
        assert definition.name == name
        assert definition.status is FormulaStatus.LOCKED


def test_locked_strategy_formula_cannot_execute() -> None:
    with pytest.raises(RuntimeError, match="not executable"):
        require_implemented("F-114")
