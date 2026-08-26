import pytest

from app.engines.adaptive_edge.decision_operators import (
    DecisionOperatorError,
    TargetStopEstimate,
    entry_gate,
    no_trade_from_conservative_ev,
    select_max_conservative_ev,
    select_target_stop,
    target_stop_expected_value,
)


def test_target_stop_expected_value_matches_canonical_equation():
    estimate = TargetStopEstimate("c1", 0.6, 10.0, 0.3, 8.0, 1.0)
    assert target_stop_expected_value(estimate) == pytest.approx(3.2)


def test_target_stop_probability_inputs_are_bounded():
    with pytest.raises(DecisionOperatorError):
        TargetStopEstimate("c1", 1.1, 10.0, 0.2, 5.0, 1.0)


def test_argmax_selects_maximum_supplied_conservative_ev():
    selected = select_max_conservative_ev((
        ("a", 1.0),
        ("b", 2.5),
        ("c", 2.0),
    ))
    assert selected.candidate_id == "b"
    assert selected.conservative_ev == pytest.approx(2.5)


def test_target_stop_selection_requires_one_value_per_candidate():
    candidates = (
        TargetStopEstimate("a", 0.5, 5, 0.2, 3, 0.5),
        TargetStopEstimate("b", 0.6, 6, 0.2, 3, 0.5),
    )
    with pytest.raises(DecisionOperatorError):
        select_target_stop(candidates, (1.0,))


def test_non_positive_conservative_ev_is_no_trade():
    assert no_trade_from_conservative_ev(0.0) is True
    assert no_trade_from_conservative_ev(-1.0) is True
    assert no_trade_from_conservative_ev(0.1) is False


def test_entry_gate_is_strictly_conjunctive():
    base = dict(
        data_ok=True,
        directional_edge_ok=True,
        expected_ev=1.0,
        conservative_ev=0.5,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    assert entry_gate(**base) is True
    for key in ("data_ok", "directional_edge_ok", "liquidity_ok", "slippage_ok", "risk_ok"):
        candidate = dict(base)
        candidate[key] = False
        assert entry_gate(**candidate) is False
    candidate = dict(base)
    candidate["expected_ev"] = 0.0
    assert entry_gate(**candidate) is False
    candidate = dict(base)
    candidate["conservative_ev"] = 0.0
    assert entry_gate(**candidate) is False
