import pytest

from app.engines.adaptive_edge.contracts import DynamicMode
from app.engines.adaptive_edge.model import (
    MarketFeatures,
    OptionCandidate,
    f101_feature_score,
    f102_edge_score,
    f103_opportunity,
    f104_dynamic_mode,
    f105_profit_protection,
    f106_dynamic_risk,
    f107_risk_per_unit,
    f108_position_size,
    f109_option_selection,
    f110_entry_trigger,
    f111_exit_trigger,
    f112_protection_parameters,
    f113_reentry_trigger,
    f114_position_interaction,
)


def test_f101_is_bounded_and_directional():
    assert f101_feature_score(MarketFeatures(2, 2, 2, 2, 100, 1)) == 1
    assert f101_feature_score(MarketFeatures(-2, -2, -2, -2, 100, 1)) == -1


def test_f102_preserves_direction_and_is_bounded():
    assert f102_edge_score(-1) < 0 < f102_edge_score(1)
    assert -1 < f102_edge_score(1) < 1


def test_f103_requires_positive_economics():
    rejected = f103_opportunity(edge_score=0.8, confidence=0.9, expected_move=10, execution_cost=8)
    accepted = f103_opportunity(edge_score=0.8, confidence=0.9, expected_move=20, execution_cost=8)
    assert not rejected.eligible
    assert accepted.eligible


def test_f104_late_session_is_exit_only_without_touching_risk():
    assert f104_dynamic_mode(edge_score=0.9, confidence=0.9, stale=False, late_session=True) is DynamicMode.EXIT_ONLY


def test_f105_protects_fraction_of_peak_profit():
    floor, giveback = f105_profit_protection(peak_pnl=1000, current_pnl=600, giveback_fraction=0.35)
    assert floor == 650
    assert giveback == 400


def test_f106_more_volatility_cannot_increase_risk():
    low_vol = f106_dynamic_risk(base_risk=1000, confidence=0.8, volatility_ratio=1, drawdown_ratio=0)
    high_vol = f106_dynamic_risk(base_risk=1000, confidence=0.8, volatility_ratio=2, drawdown_ratio=0)
    assert high_vol.authorized_risk <= low_vol.authorized_risk


def test_f107_risk_per_unit_includes_stop_distance_and_cost():
    assert f107_risk_per_unit(entry_price=100, stop_price=95, point_value=10, estimated_cost=2) == 52


def test_f108_never_exceeds_authorized_risk():
    assert f108_position_size(authorized_risk=100, risk_per_unit=26, lot_size=1) == 3
    assert f108_position_size(authorized_risk=0, risk_per_unit=26, lot_size=1) == 0


def test_f109_selects_a_candidate_or_none():
    selected = f109_option_selection((
        OptionCandidate("A", 0.55, 0.02, 1.5, 0.10, 0.9),
        OptionCandidate("B", 0.30, 0.01, 2.0, 0.20, 0.8),
    ), 1)
    assert selected.symbol == "A"
    assert selected.score > 0


def test_f110_requires_eligible_opportunity_and_liquidity():
    opp = f103_opportunity(edge_score=0.8, confidence=0.9, expected_move=20, execution_cost=5)
    assert f110_entry_trigger(opportunity=opp, mode=DynamicMode.ACTIVE, option_score=0.8)
    assert not f110_entry_trigger(opportunity=opp, mode=DynamicMode.DEFENSIVE, option_score=0.8)


def test_f111_exits_on_edge_reversal_or_protection_breach():
    assert f111_exit_trigger(direction=1, edge_score=-0.2, current_pnl=100, protection_floor=50)
    assert f111_exit_trigger(direction=1, edge_score=0.5, current_pnl=40, protection_floor=50)


def test_f112_stronger_edge_has_wider_target_but_tighter_stop():
    weak_stop, weak_target = f112_protection_parameters(entry_price=100, atr=4, edge_score=0.2)
    strong_stop, strong_target = f112_protection_parameters(entry_price=100, atr=4, edge_score=0.9)
    assert strong_stop > weak_stop
    assert strong_target > weak_target


def test_f113_requires_fresh_stronger_edge():
    assert f113_reentry_trigger(was_exited=True, fresh_edge_score=0.8, prior_edge_score=0.6, cooldown_elapsed=True)
    assert not f113_reentry_trigger(was_exited=True, fresh_edge_score=0.6, prior_edge_score=0.8, cooldown_elapsed=True)


def test_f114_caps_new_risk_by_remaining_budget_and_correlation():
    assert f114_position_interaction(existing_risk=400, new_risk=300, total_risk_budget=1000) == 300
    assert f114_position_interaction(existing_risk=900, new_risk=300, total_risk_budget=1000) == 100
    assert f114_position_interaction(existing_risk=400, new_risk=300, total_risk_budget=1000, correlation_penalty=0.5) == 150
