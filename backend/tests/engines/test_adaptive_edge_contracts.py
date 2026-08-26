from app.engines.adaptive_edge.contracts import (
    AdaptiveEdgeState,
    DynamicMode,
    RiskAuthorization,
    RiskState,
)


def test_mode_transition_does_not_mutate_authorization():
    authorization = RiskAuthorization(
        opportunity_id="o1",
        authorized_risk=500.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="1.0",
        issued_at="2026-08-11T10:00:00",
    )
    state = AdaptiveEdgeState(
        mode=DynamicMode.ACTIVE,
        risk_state=RiskState.AUTHORIZED,
        authorization=authorization,
    )
    changed = state.with_mode(DynamicMode.INTRADAY)
    assert changed.authorization == authorization
    assert changed.authorization.authorized_risk == 500.0
