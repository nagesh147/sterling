from app.engines.adaptive_edge.f103_opportunity import (
    OpportunityAction,
    OpportunityCandidate,
    evaluate_opportunity,
)


def candidate(**overrides):
    values = dict(
        action=OpportunityAction.BUY_CE,
        data_ok=True,
        directional_edge_ok=True,
        expected_value=100.0,
        conservative_expected_value=50.0,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    values.update(overrides)
    return OpportunityCandidate(**values)


def test_f103_authorizes_only_when_all_mandatory_gates_pass() -> None:
    result = evaluate_opportunity(candidate())
    assert result.eligible is True
    assert result.action is OpportunityAction.BUY_CE
    assert result.reason == "all_mandatory_gates_passed"


def test_f103_fails_closed_on_non_positive_conservative_ev() -> None:
    result = evaluate_opportunity(candidate(conservative_expected_value=0.0))
    assert result.eligible is False
    assert result.action is OpportunityAction.NO_TRADE
    assert result.reason == "conservative_expected_value_non_positive"


def test_f103_fails_closed_on_missing_expected_value() -> None:
    result = evaluate_opportunity(candidate(expected_value=None))
    assert result.eligible is False
    assert result.reason == "missing_expected_value"


def test_f103_fails_closed_on_any_execution_quality_gate() -> None:
    for field in ("data_ok", "directional_edge_ok", "liquidity_ok", "slippage_ok", "risk_ok"):
        result = evaluate_opportunity(candidate(**{field: False}))
        assert result.eligible is False
        assert result.action is OpportunityAction.NO_TRADE


def test_f103_is_deterministic() -> None:
    c = candidate(action=OpportunityAction.BUY_PE)
    assert evaluate_opportunity(c) == evaluate_opportunity(c)
