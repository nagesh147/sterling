from datetime import datetime, timezone

from app.engines.adaptive_edge.canonical_math import ExecutionCost
from app.engines.adaptive_edge.economic_engine import evaluate
from app.engines.adaptive_edge.protection_engine import update_protection
from app.engines.adaptive_edge.risk_engine import authorize, tighten


def test_economic_layer_uses_conservative_net_value():
    result = evaluate(
        expected_gross_value=100.0,
        execution_cost=ExecutionCost(spread=5.0, slippage=2.0),
        conservative_net_value=20.0,
        effective_risk=10.0,
    )
    assert result.expected_net_value == 93.0
    assert result.eligible is True
    assert result.ev_per_risk == 2.0


def test_risk_authorization_can_only_tighten():
    authorization = authorize(
        authorization_id="RA-1",
        opportunity_id="OP-1",
        authorization_time=datetime.now(timezone.utc),
        authorized_risk=100.0,
        entry_price=100.0,
        initial_stop=95.0,
        point_value=1.0,
        effective_execution_cost_per_unit=0.5,
        risk_policy_version="1.0",
    )
    assert authorization.resized_quantity(10) == 10
    tightened = tighten(authorization, 60.0)
    assert tightened.authorized_risk == 60.0
    assert tighten(tightened, 90.0).authorized_risk == 60.0


def test_profit_protection_stop_never_looses():
    state = update_protection(
        peak_profit=100.0,
        current_profit=80.0,
        peak_price=150.0,
        allowed_giveback=20.0,
        previous_stop=120.0,
        candidate_dynamic_boundary=110.0,
        original_risk_boundary=100.0,
    )
    assert state.giveback == 20.0
    assert state.floor_price == 130.0
    assert state.stop_price == 130.0
