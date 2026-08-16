import pytest

from app.engines.adaptive_edge.execution_gate import (
    REQUIRED_STRATEGY_FORMULAS,
    ExecutionBlockedError,
    ExecutionGateStatus,
    evaluate_execution_gate,
    require_execution_authorized,
)


def test_all_strategy_specific_formulas_are_required():
    assert REQUIRED_STRATEGY_FORMULAS == tuple(
        f"F-{number:03d}" for number in range(101, 115)
    )


def test_current_adaptive_edge_is_authorized():
    decision = evaluate_execution_gate()

    assert decision.status is ExecutionGateStatus.AUTHORIZED
    assert decision.authorized is True
    assert decision.blocking_formulas == ()
    assert decision.reason is None


def test_unknown_formula_is_fail_closed():
    decision = evaluate_execution_gate(("F-999",))

    assert decision.status is ExecutionGateStatus.BLOCKED
    assert decision.blocking_formulas == ("F-999",)


def test_gate_raises_when_execution_is_not_authorized():
    with pytest.raises(ExecutionBlockedError) as exc_info:
        require_execution_authorized(("F-999",))

    assert exc_info.value.decision.blocking_formulas == ("F-999",)


def test_gate_can_authorize_a_fully_implemented_registry_subset():
    decision = evaluate_execution_gate(("F-004",))

    assert decision.status is ExecutionGateStatus.AUTHORIZED
    assert decision.authorized is True
    assert decision.blocking_formulas == ()


def test_friction_expectancy_gate_authorizes_viable_trade():
    from app.engines.adaptive_edge.execution_gate import evaluate_friction_expectancy_gate

    # 1 lot NIFTY (25 qty), Entry 100, Target 150 (gain = 50 * 25 = 1250 INR > 240)
    decision = evaluate_friction_expectancy_gate(
        entry_price=100.0,
        target_price=150.0,
        lot_size=25,
        estimated_friction_inr=60.0,
        min_friction_multiplier=4.0,
    )
    assert decision.authorized is True
    assert decision.expected_gain_inr == 1250.0
    assert decision.friction_ratio == 20.83
    assert decision.reason is None


def test_friction_expectancy_gate_blocks_low_expectancy_trade():
    from app.engines.adaptive_edge.execution_gate import evaluate_friction_expectancy_gate

    # 1 lot NIFTY (25 qty), Entry 100, Target 105 (gain = 5 * 25 = 125 INR < 240)
    decision = evaluate_friction_expectancy_gate(
        entry_price=100.0,
        target_price=105.0,
        lot_size=25,
        estimated_friction_inr=60.0,
        min_friction_multiplier=4.0,
    )
    assert decision.authorized is False
    assert decision.expected_gain_inr == 125.0
    assert decision.friction_ratio == 2.08
    assert "expected_gain_below_friction_threshold" in decision.reason


def test_bid_ask_spread_gate_blocks_wide_spread():
    from app.engines.adaptive_edge.execution_gate import evaluate_bid_ask_spread_gate

    # Bid 100, Ask 105 (spread = 5 pts > 3.0 max, pct = 4.88% > 3.0%)
    decision = evaluate_bid_ask_spread_gate(bid=100.0, ask=105.0)
    assert decision.authorized is False
    assert decision.spread_pts == 5.0
    assert "wide_bid_ask_spread_slippage_risk" in decision.reason

    # Tight spread: Bid 100.0, Ask 100.5 (spread = 0.5 pts, pct = 0.5%)
    ok = evaluate_bid_ask_spread_gate(bid=100.0, ask=100.5)
    assert ok.authorized is True
    assert ok.spread_pts == 0.5
    assert ok.reason is None


def test_vega_iv_gate_blocks_extreme_iv_spike():
    from app.engines.adaptive_edge.execution_gate import evaluate_vega_iv_gate

    # Peak IV Rank = 85 (above 75 threshold) -> block naked buy, recommend vertical spread
    decision = evaluate_vega_iv_gate(iv_rank=85.0)
    assert decision.authorized is False
    assert decision.is_high_vega_risk is True
    assert decision.recommended_structure == "VERTICAL_SPREAD"
    assert "extreme_iv_rank_vega_crush_risk" in decision.reason

    # Normal IV Rank = 42 -> authorized for naked option
    ok = evaluate_vega_iv_gate(iv_rank=42.0)
    assert ok.authorized is True
    assert ok.is_high_vega_risk is False
    assert ok.recommended_structure == "NAKED_OPTION"


def test_anti_chase_gate_blocks_extended_sweep():
    from app.engines.adaptive_edge.execution_gate import evaluate_anti_chase_gate

    # Current Price 24600, POC Anchor 24500 (dist = 100 pts), ATR = 40 (dist = 2.5 ATR > 1.5 limit)
    decision = evaluate_anti_chase_gate(current_price=24600.0, anchor_price=24500.0, atr=40.0)
    assert decision.authorized is False
    assert decision.atr_ratio == 2.5
    assert "chase_extended_pullback_required" in decision.reason

    # Contained move: Current 24530, Anchor 24500 (dist = 30 pts, 0.75 ATR <= 1.5)
    ok = evaluate_anti_chase_gate(current_price=24530.0, anchor_price=24500.0, atr=40.0)
    assert ok.authorized is True
    assert ok.atr_ratio == 0.75


def test_dte_gamma_gate_blocks_otm_on_expiry_day():
    from app.engines.adaptive_edge.execution_gate import evaluate_dte_gamma_gate

    # 0 DTE Expiry Day with OTM2 leg -> blocked due to violent gamma whipsaw
    decision = evaluate_dte_gamma_gate(dte=0, moneyness="OTM2", delta=0.25)
    assert decision.authorized is False
    assert decision.is_expiry_day is True
    assert "0_or_1_dte_otm_gamma_whipsaw_blocked" in decision.reason

    # 0 DTE with ITM1 leg (Delta 0.65) -> authorized
    ok = evaluate_dte_gamma_gate(dte=0, moneyness="ITM1", delta=0.65)
    assert ok.authorized is True
    assert ok.is_expiry_day is True
    assert ok.reason is None

    # Normal 12 DTE with OTM1 leg -> authorized
    normal = evaluate_dte_gamma_gate(dte=12, moneyness="OTM1", delta=0.40)
    assert normal.authorized is True
    assert normal.is_expiry_day is False


def test_portfolio_drawdown_gate_trips_breaker():
    from app.engines.adaptive_edge.execution_gate import evaluate_portfolio_drawdown_gate

    # Account 10 Lakhs, daily loss -35,000 INR (3.5% > 3.0% max limit) -> trips breaker
    decision = evaluate_portfolio_drawdown_gate(
        daily_realized_pnl=-25000.0,
        daily_unrealized_pnl=-10000.0,
        portfolio_equity=1000000.0,
        max_drawdown_pct=3.0,
    )
    assert decision.authorized is False
    assert decision.circuit_breaker_tripped is True
    assert decision.current_drawdown_pct == 3.5
    assert "daily_drawdown_circuit_breaker_tripped" in decision.reason

    # Normal day: PnL +15,000 INR -> authorized
    ok = evaluate_portfolio_drawdown_gate(
        daily_realized_pnl=15000.0,
        daily_unrealized_pnl=0.0,
        portfolio_equity=1000000.0,
    )
    assert ok.authorized is True
    assert ok.circuit_breaker_tripped is False

    # Disabled toggle: returns authorized even on large loss
    disabled = evaluate_portfolio_drawdown_gate(
        daily_realized_pnl=-50000.0,
        daily_unrealized_pnl=0.0,
        portfolio_equity=1000000.0,
        enabled=False,
    )
    assert disabled.authorized is True
    assert disabled.circuit_breaker_tripped is False

    # Custom threshold (e.g. 5.0%): loss of 3.5% is authorized
    custom = evaluate_portfolio_drawdown_gate(
        daily_realized_pnl=-35000.0,
        daily_unrealized_pnl=0.0,
        portfolio_equity=1000000.0,
        max_drawdown_pct=5.0,
        enabled=True,
    )
    assert custom.authorized is True
    assert custom.circuit_breaker_tripped is False


def test_portfolio_var_gate_monitors_risk():
    from app.engines.adaptive_edge.execution_gate import evaluate_portfolio_var_gate

    # Portfolio 5 Lakhs, large open positions with high volatility -> VaR > 2.5% budget
    decision = evaluate_portfolio_var_gate(
        portfolio_equity=500000.0,
        position_values=[200000.0, 150000.0],
        position_volatilities=[0.03, 0.04],
        confidence=0.99,
        max_var_pct=2.5,
    )
    assert decision.authorized is False
    assert decision.portfolio_var_pct > 2.5
    assert "portfolio_var_exceeds_risk_budget" in decision.reason

    # Small contained position -> VaR within limit
    ok = evaluate_portfolio_var_gate(
        portfolio_equity=500000.0,
        position_values=[50000.0],
        position_volatilities=[0.02],
        confidence=0.99,
        max_var_pct=2.5,
    )
    assert ok.authorized is True
    assert ok.portfolio_var_pct < 2.5


def test_smart_iceberg_slicing():
    from app.engines.adaptive_edge.execution_gate import evaluate_smart_iceberg_slicing

    # Order of 1000 qty NIFTY (40 lots) -> sliced into 4 clips of 250 qty (10 lots)
    decision = evaluate_smart_iceberg_slicing(quantity=1000, freeze_limit=1800, max_clip_lots=10, lot_size=25)
    assert decision.requires_slicing is True
    assert decision.num_legs == 4
    assert decision.clip_quantity == 250

    # Small order of 50 qty (2 lots) -> no slicing needed
    single = evaluate_smart_iceberg_slicing(quantity=50, freeze_limit=1800, max_clip_lots=10, lot_size=25)
    assert single.requires_slicing is False
    assert single.num_legs == 1
    assert single.clip_quantity == 50


def test_alpha_conviction_gate():
    from app.engines.adaptive_edge.execution_gate import evaluate_alpha_conviction_gate

    # High confluence A+ trade -> authorized
    decision = evaluate_alpha_conviction_gate(confluence_score=88.0, volume_surge=2.1, adx=28.0)
    assert decision.authorized is True
    assert decision.grade == "A+"
    assert decision.reason is None

    # Low confluence C grade chop trade -> blocked
    blocked = evaluate_alpha_conviction_gate(confluence_score=55.0, volume_surge=1.1, adx=14.0)
    assert blocked.authorized is False
    assert blocked.grade == "C"
    assert "insufficient_alpha_conviction" in blocked.reason


