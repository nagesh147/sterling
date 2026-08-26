import pytest

from app.engines.adaptive_edge.strategy_v21 import (
    Direction,
    OperatingMode,
    OptionCandidate,
    StrategyDefinitionError,
    StrategyParameters,
    f101_feature_score,
    f102_edge_score,
    f103_opportunity_eligibility,
    f104_dynamic_mode,
    f105_profit_protection,
    f106_dynamic_risk,
    f107_risk_per_unit,
    f108_position_sizing,
    f109_instrument_selection,
    f110_entry_trigger,
    f111_exit_trigger,
    f112_protection_parameters,
    f113_reentry,
    f114_multi_position_interaction,
)


def test_f101_normalizes_and_bounds_score():
    p = StrategyParameters()
    assert -1.0 <= f101_feature_score((10, -10, 5, -5), p) <= 1.0
    assert f101_feature_score((0, 0, 0, 0), p) == pytest.approx(0.0)


def test_f102_produces_valid_three_state_probability_and_direction():
    result = f102_edge_score((2, 2, 2, 2), StrategyParameters())
    assert result.p_up + result.p_down + result.p_neutral == pytest.approx(1.0)
    assert all(0 <= value <= 1 for value in (result.p_up, result.p_down, result.p_neutral))
    assert result.direction is Direction.UP


def test_f103_fails_closed_on_missing_data_and_disabled_mode():
    edge = f102_edge_score((2, 2, 2, 2), StrategyParameters())
    result = f103_opportunity_eligibility(edge, 10, data_quality_ok=False, mode=OperatingMode.DISABLED, p=StrategyParameters())
    assert not result.eligible
    assert "data_quality_invalid" in result.reasons
    assert "mode_disabled" in result.reasons


def test_f104_mode_is_monotonic_with_risk_degradation():
    p = StrategyParameters()
    assert f104_dynamic_mode(volatility_ratio=1.0, drawdown_fraction=0.0, data_quality_ok=True, p=p) is OperatingMode.NORMAL
    assert f104_dynamic_mode(volatility_ratio=1.5, drawdown_fraction=0.0, data_quality_ok=True, p=p) is OperatingMode.RESTRICTED
    assert f104_dynamic_mode(volatility_ratio=2.5, drawdown_fraction=0.0, data_quality_ok=True, p=p) is OperatingMode.DISABLED


def test_f105_protection_is_monotonic_for_long_and_short():
    p = StrategyParameters()
    long_1 = f105_profit_protection(direction=Direction.UP, entry_price=100, favorable_extreme=102, previous_stop=None, p=p)
    long_2 = f105_profit_protection(direction=Direction.UP, entry_price=100, favorable_extreme=105, previous_stop=long_1, p=p)
    assert long_2 >= long_1

    short_1 = f105_profit_protection(direction=Direction.DOWN, entry_price=100, favorable_extreme=98, previous_stop=None, p=p)
    short_2 = f105_profit_protection(direction=Direction.DOWN, entry_price=100, favorable_extreme=95, previous_stop=short_1, p=p)
    assert short_2 <= short_1


def test_f106_dynamic_risk_is_capped_and_disabled_is_zero():
    p = StrategyParameters(maximum_risk=100)
    # f106_dynamic_risk is keyword-only, like every other F-1xx in strategy_v21.
    assert f106_dynamic_risk(authorized_base_risk=200, edge_strength=1, mode=OperatingMode.NORMAL, p=p) == pytest.approx(100)
    assert f106_dynamic_risk(authorized_base_risk=200, edge_strength=1, mode=OperatingMode.DISABLED, p=p) == pytest.approx(0)


def test_f107_risk_per_unit_includes_explicit_costs():
    p = StrategyParameters(minimum_risk_per_unit=0.01)
    assert f107_risk_per_unit(entry_price=100, protection_price=98, contract_multiplier=50, entry_cost_per_unit=0.1, exit_cost_per_unit=0.1, p=p) == pytest.approx(110)


def test_f108_sizing_never_exceeds_authorized_risk():
    result = f108_position_sizing(authorized_risk=100, risk_per_unit=30, quantity_increment=10, minimum_quantity=10, maximum_quantity=100)
    assert result.quantity == 0
    result = f108_position_sizing(authorized_risk=300, risk_per_unit=30, quantity_increment=10, minimum_quantity=10, maximum_quantity=100)
    assert result.quantity == 10
    assert result.quantity * result.risk_per_unit <= result.authorized_risk


def test_f109_selects_directional_option_only():
    candidates = [
        OptionCandidate("ce", "CE", 10, 100, 98, 50, 50, 50, 500),
        OptionCandidate("pe", "PE", 100, 100, 98, 50, 50, 50, 500),
    ]
    assert f109_instrument_selection(candidates, Direction.UP).instrument_id == "ce"


def test_f110_and_f111_are_directional():
    assert f110_entry_trigger(direction=Direction.UP, underlying_price=101, trigger_price=100)
    assert f110_entry_trigger(direction=Direction.DOWN, underlying_price=99, trigger_price=100)
    assert f111_exit_trigger(direction=Direction.UP, current_price=98, stop_price=99, target_price=104, horizon_expired=False)
    assert f111_exit_trigger(direction=Direction.DOWN, current_price=105, stop_price=104, target_price=96, horizon_expired=False)
    assert f111_exit_trigger(direction=Direction.UP, current_price=100, stop_price=90, target_price=120, horizon_expired=True)


def test_f112_protection_parameters_are_explicit():
    result = f112_protection_parameters(direction=Direction.UP, entry_price=100, p=StrategyParameters(initial_stop_distance=2, target_multiple=3))
    assert result.initial_stop_distance == 2
    assert result.target_distance == 6


def test_f113_reentry_requires_new_opportunity_and_cooldown():
    p = StrategyParameters(maximum_reentries=1, reentry_cooldown_bars=2)
    assert not f113_reentry(prior_exit_bar=10, current_bar=11, reentry_count=0, new_opportunity=True, p=p).allowed
    assert f113_reentry(prior_exit_bar=10, current_bar=12, reentry_count=0, new_opportunity=True, p=p).allowed
    assert not f113_reentry(prior_exit_bar=10, current_bar=12, reentry_count=1, new_opportunity=True, p=p).allowed


def test_f114_enforces_shared_capacity_and_position_count():
    p = StrategyParameters(maximum_risk=100, portfolio_risk_fraction=1.0, maximum_positions=2)
    assert f114_multi_position_interaction(existing_positions=1, existing_risk=40, candidate_risk=50, p=p).allowed
    assert not f114_multi_position_interaction(existing_positions=1, existing_risk=60, candidate_risk=50, p=p).allowed
    assert not f114_multi_position_interaction(existing_positions=2, existing_risk=20, candidate_risk=10, p=p).allowed


def test_invalid_parameter_dimensions_are_rejected():
    with pytest.raises(StrategyDefinitionError):
        StrategyParameters(feature_means=(0,), feature_scales=(1, 1), feature_weights=(1, 1))
