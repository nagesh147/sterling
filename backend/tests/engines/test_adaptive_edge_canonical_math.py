from app.engines.adaptive_edge.canonical_math import (
    ExecutionCost,
    acceleration,
    aggressor,
    conditional_percentile,
    continuation_value,
    cumulative_delta,
    delta,
    expected_net_value,
    expected_value_per_risk,
    incremental_volume,
    liquidity_imbalance,
    maximum_accepted_risk,
    mid,
    monotonic_stop,
    multinomial_logistic,
    normalized_return,
    position_size,
    price_change,
    profit_floor,
    profit_giveback,
    relative_spread,
    return_,
    risk_per_unit,
    similarity_distance,
    similarity_weight,
    spread,
    target_stop_ev,
    velocity,
    volume_intensity,
)


def test_price_operators_match_specification():
    assert mid(99, 101) == 100
    assert spread(99, 101) == 2
    assert relative_spread(99, 101) == 0.02
    assert price_change(105, 100) == 5
    assert return_(105, 100) == 0.05
    assert velocity(5, 2) == 2.5
    assert acceleration(4, 2) == 2


def test_aggressor_unknown_is_not_forced_into_direction():
    assert aggressor(101, 99, 101) == "BUY"
    assert aggressor(99, 99, 101) == "SELL"
    assert aggressor(100, 99, 101) == "UNKNOWN"


def test_delta_and_volume_reset():
    assert incremental_volume(120, 100) == 20
    assert incremental_volume(90, 100) is None
    assert delta(80, 30) == 50
    assert cumulative_delta(100, -20) == 80


def test_liquidity_and_volume_are_parameterized():
    assert liquidity_imbalance(60, 40) == 0.2
    assert volume_intensity(150, 100) == 1.5


def test_conditional_normalization_uses_only_supplied_history():
    assert conditional_percentile(3, [1, 2, 3, 4]) == 0.75
    assert normalized_return(0.02, 0.01) == 2.0


def test_logistic_probabilities_sum_to_one():
    probabilities = multinomial_logistic([1.0, 2.0], [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
    assert abs(sum(probabilities) - 1.0) < 1e-12


def test_similarity_operator_is_deterministic():
    distance = similarity_distance([0.0, 1.0], [1.0, 1.0], [1.0, 2.0])
    assert distance == 1.0
    assert similarity_weight(distance, 1.0) == __import__("math").exp(-1.0)


def test_economic_value_is_net_of_costs_and_cost_monotonic():
    cheap = ExecutionCost(spread=1.0)
    expensive = ExecutionCost(spread=3.0)
    assert expected_net_value(10.0, cheap) > expected_net_value(10.0, expensive)


def test_risk_and_sizing_respect_authorization():
    unit_risk = risk_per_unit(100.0, 95.0, 1.0, 0.5)
    assert unit_risk == 5.5
    assert position_size(100.0, unit_risk, 10) == 10
    assert maximum_accepted_risk(100.0, 150.0) == 100.0


def test_profit_protection_is_monotonic():
    assert profit_giveback(100.0, 70.0) == 30.0
    assert profit_floor(120.0, 30.0) == 90.0
    assert monotonic_stop(100.0, 105.0) == 105.0
    assert monotonic_stop(105.0, 100.0) == 105.0


def test_continuation_and_trade_economics():
    assert continuation_value(100.0, 40.0, 10.0) == 50.0
    assert expected_value_per_risk(50.0, 25.0) == 2.0
    assert target_stop_ev(0.6, 100.0, 0.3, 50.0, 10.0) == 35.0
