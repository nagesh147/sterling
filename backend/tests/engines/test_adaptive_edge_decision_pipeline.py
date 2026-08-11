from app.engines.adaptive_edge.canonical_math import ExecutionCost
from app.engines.adaptive_edge.decision_pipeline import (
    OutcomeEstimate,
    TargetStopCandidate,
    TradeEconomics,
    evaluate_candidate,
    evaluate_target_stop_candidate,
    score_target_stop_candidates,
)


def test_positive_net_and_conservative_value_is_actionable():
    decision = evaluate_candidate(
        OutcomeEstimate(1, 0.7, 100.0, 0.3, 40.0),
        TradeEconomics(80.0, ExecutionCost(spread=5.0), 60.0, 20.0),
    )
    assert decision.actionable
    assert decision.value_per_risk == 3.0


def test_cost_can_turn_positive_gross_value_into_no_trade():
    decision = evaluate_candidate(
        OutcomeEstimate(1, 0.7, 50.0, 0.3, 20.0),
        TradeEconomics(20.0, ExecutionCost(spread=20.0), 10.0, 10.0),
    )
    assert not decision.actionable
    assert decision.reason == "expected_net_value_non_positive"


def test_target_stop_selection_uses_highest_positive_conservative_ev():
    candidates = (
        TargetStopCandidate("t1", "s1", 0.6, 20, 0.4, 10, 2, 5),
        TargetStopCandidate("t2", "s2", 0.7, 30, 0.3, 10, 2, 9),
    )
    selected, reason = score_target_stop_candidates(candidates)
    assert selected is candidates[1]
    assert reason == "selected_highest_conservative_ev"


def test_target_stop_equation_is_recomputed_for_audit():
    candidate = TargetStopCandidate("t", "s", 0.7, 30, 0.3, 10, 2, 0)
    assert evaluate_target_stop_candidate(candidate) == 16.0
