from app.engines.adaptive_edge.contracts import (
    AdaptiveEdgeState,
    DynamicMode,
    OpportunityState,
    RiskAuthorization,
    RiskState,
)
from app.engines.adaptive_edge.state import StateEvent, transition


def _state() -> AdaptiveEdgeState:
    authorization = RiskAuthorization(
        opportunity_id="opp-1",
        authorized_risk=1000.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="risk-1",
        issued_at="2026-08-11T00:00:00Z",
    )
    return AdaptiveEdgeState(
        mode=DynamicMode.ACTIVE,
        risk_state=RiskState.AUTHORIZED,
        opportunity_state=OpportunityState.VALIDATED,
        authorization=authorization,
    )


def test_mode_transition_preserves_risk_authorization_identity():
    state = _state()
    result = transition(state, StateEvent.ENTER_INTRADAY).resulting_state

    assert result.mode is DynamicMode.INTRADAY
    assert result.authorization is state.authorization
    assert result.authorization.authorized_risk == 1000.0
    assert result.risk_state is RiskState.AUTHORIZED


def test_defensive_transition_cannot_reduce_or_increase_authorized_risk_implicitly():
    state = _state()
    result = transition(state, StateEvent.DEFENSIVE).resulting_state

    assert result.mode is DynamicMode.DEFENSIVE
    assert result.authorization is state.authorization
    assert result.authorization.authorized_risk == 1000.0


def test_halt_does_not_delete_authorization_but_freezes_risk_state():
    state = _state()
    result = transition(state, StateEvent.HALT).resulting_state

    assert result.mode is DynamicMode.HALTED
    assert result.risk_state is RiskState.HALTED
    assert result.authorization is state.authorization
