import pytest
from app.engines.risk.greeks_budget import bsm_greeks, GreeksBudgetChecker, GreeksBudget, PositionGreeks


def test_bsm_delta_call_atm():
    g = bsm_greeks(S=100, K=100, T=0.1, r=0.0, sigma=0.8, is_call=True)
    # ATM call delta ≈ 0.5 (not exact due to vol smile)
    assert 0.4 <= g.delta <= 0.6


def test_bsm_vega_positive():
    g = bsm_greeks(S=100, K=100, T=0.1, r=0.0, sigma=0.8, is_call=True)
    assert g.vega > 0.0


def test_budget_delta_breach():
    budget = GreeksBudget(max_net_delta=0.30, max_net_vega=0.15, max_net_theta=-0.02)
    checker = GreeksBudgetChecker(budget, portfolio_value=100_000.0)
    # New position with huge delta
    large_greeks = PositionGreeks(delta=5.0, vega=0.0, theta=0.0)
    allowed, reason = checker.check([], large_greeks, new_position_notional=100_000.0)
    assert not allowed
    assert 'delta_breach' in reason


def test_budget_allows_within_limits():
    budget = GreeksBudget(max_net_delta=0.30, max_net_vega=0.15, max_net_theta=-0.02)
    checker = GreeksBudgetChecker(budget, portfolio_value=100_000.0)
    small_greeks = PositionGreeks(delta=0.10, vega=0.05, theta=-0.001)
    allowed, reason = checker.check([], small_greeks, new_position_notional=10_000.0)
    assert allowed
    assert reason == 'ok'
