from __future__ import annotations

from app.engines.adaptive_edge.formula_registry import FormulaStatus, get_formula


def test_f109_f114_registry_roles_match_canonical_contract() -> None:
    expected = {
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
