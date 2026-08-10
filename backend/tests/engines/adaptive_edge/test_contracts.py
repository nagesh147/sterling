from app.engines.adaptive_edge.contracts import (
    AdaptiveEdgeState,
    DynamicMode,
    RiskAuthorization,
    RiskState,
)


def test_mode_transition_does_not_change_authorized_risk():
    authorization = RiskAuthorization(
        opportunity_id="opp-1",
        authorized_risk=1000.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="risk-1",
        issued_at="2026-08-11T00:00:00Z",
    )
    state = AdaptiveEdgeState(
        mode=DynamicMode.ACTIVE,
        risk_state=RiskState.AUTHORIZED,
        authorization=authorization,
    )

    changed = state.with_mode(DynamicMode.INTRADAY)

    assert changed.mode is DynamicMode.INTRADAY
    assert changed.authorization is authorization
    assert changed.authorization.authorized_risk == 1000.0
    assert changed.risk_state is RiskState.AUTHORIZED


def test_risk_authorization_is_immutable():
    authorization = RiskAuthorization(
        opportunity_id="opp-1",
        authorized_risk=1000.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="risk-1",
        issued_at="2026-08-11T00:00:00Z",
    )

    try:
        authorization.authorized_risk = 2000.0
    except AttributeError:
        pass
    else:
        raise AssertionError("risk authorization must be immutable")
