import pytest

from app.engines.adaptive_edge.e2e import PositionState
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.lifecycle_engine import (
    A126LifecycleEngine,
    HorizonState,
    LifecycleAction,
    LifecycleEvidence,
    OverlayState,
    ProtectionState,
    ThesisState,
)


def make_position(qty: int = 50, avg_price: float = 100.0) -> PositionState:
    return PositionState(
        position_id="pos-1",
        instrument_id="NIFTY-CE",
        quantity=qty,
        average_price=avg_price,
        lifecycle_state="OPEN",
        source_execution_event_id="ex-1",
    )


def test_fast_failure_hard_risk_breach_forces_immediate_exit():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
    pos = make_position()
    evidence = LifecycleEvidence(hard_risk_breached=True)

    eval_result = engine.evaluate_with_evidence(pos, evidence, "2026-08-14T03:45:00+00:00")
    assert eval_result.action == LifecycleAction.EXIT_HARD_STOP.value
    assert eval_result.lifecycle_state == "FLAT"
    assert engine.is_active is False
    assert len(engine.transitions) == 1
    assert engine.transitions[0].trigger == "HARD_RISK_BREACH"


def test_thesis_invalidation_forces_exit_before_hard_stop():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.TACTICAL)
    pos = make_position()
    evidence = LifecycleEvidence(
        thesis_valid=False,
        thesis_state=ThesisState.THESIS_INVALID,
        hard_risk_breached=False,
    )

    eval_result = engine.evaluate_with_evidence(pos, evidence, "2026-08-14T03:46:00+00:00")
    assert eval_result.action == LifecycleAction.EXIT_THESIS_INVALID.value
    assert eval_result.lifecycle_state == "FLAT"
    assert engine.thesis_state is ThesisState.THESIS_INVALID
    assert engine.is_active is False


def test_profit_alone_cannot_promote_without_persistence_evidence():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
    pos = make_position()
    # High profit but no persistence evidence
    evidence = LifecycleEvidence(
        current_profit_r=3.5,
        persistence_evidence_valid=False,  # Persistence evidence NOT satisfied
        thesis_valid=True,
        thesis_state=ThesisState.THESIS_VALID,
    )

    eval_result = engine.evaluate_with_evidence(pos, evidence, "2026-08-14T03:47:00+00:00")
    # Must NOT promote to TACTICAL
    assert eval_result.action == LifecycleAction.HOLD.value
    assert engine.current_horizon is HorizonState.IMPULSE


def test_evidence_driven_multi_horizon_graduation():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
    pos = make_position()

    # 1. IMPULSE -> TACTICAL
    ev1 = LifecycleEvidence(persistence_evidence_valid=True, thesis_state=ThesisState.THESIS_STRONG)
    r1 = engine.evaluate_with_evidence(pos, ev1, "2026-08-14T03:50:00+00:00")
    assert r1.action == LifecycleAction.PROMOTE.value
    assert engine.current_horizon is HorizonState.TACTICAL

    # 2. TACTICAL -> INTRADAY_SWING
    ev2 = LifecycleEvidence(persistence_evidence_valid=True, thesis_state=ThesisState.THESIS_STRONG)
    r2 = engine.evaluate_with_evidence(pos, ev2, "2026-08-14T04:10:00+00:00")
    assert r2.action == LifecycleAction.PROMOTE.value
    assert engine.current_horizon is HorizonState.INTRADAY_SWING

    # 3. INTRADAY_SWING -> SESSION_TREND
    ev3 = LifecycleEvidence(persistence_evidence_valid=True, thesis_state=ThesisState.THESIS_VALID)
    r3 = engine.evaluate_with_evidence(pos, ev3, "2026-08-14T05:00:00+00:00")
    assert r3.action == LifecycleAction.PROMOTE.value
    assert engine.current_horizon is HorizonState.SESSION_TREND

    # 4. SESSION_TREND -> SESSION_EXTENSION
    ev4 = LifecycleEvidence(persistence_evidence_valid=True, thesis_state=ThesisState.THESIS_STRONG)
    r4 = engine.evaluate_with_evidence(pos, ev4, "2026-08-14T06:00:00+00:00")
    assert r4.action == LifecycleAction.PROMOTE.value
    assert engine.current_horizon is HorizonState.SESSION_EXTENSION


def test_horizon_downgrade_when_persistence_decays():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.INTRADAY_SWING)
    pos = make_position()

    # Persistence decays but thesis remains valid
    ev = LifecycleEvidence(
        persistence_decayed=True,
        thesis_state=ThesisState.THESIS_VALID,
    )
    res = engine.evaluate_with_evidence(pos, ev, "2026-08-14T04:30:00+00:00")
    assert res.action == LifecycleAction.DOWNGRADE.value
    assert engine.current_horizon is HorizonState.TACTICAL
    assert engine.is_active is True  # Downgrade does NOT force exit


def test_session_cutoff_forces_mandatory_exit():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.SESSION_TREND)
    pos = make_position()

    ev = LifecycleEvidence(session_cutoff_reached=True)
    res = engine.evaluate_with_evidence(pos, ev, "2026-08-14T09:45:00+00:00")
    assert res.action == LifecycleAction.EXIT_SESSION_CUTOFF.value
    assert res.lifecycle_state == "FLAT"
    assert engine.is_active is False


def test_data_uncertainty_overlay_blocks_promotion():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
    pos = make_position()

    ev = LifecycleEvidence(
        persistence_evidence_valid=True,
        thesis_state=ThesisState.THESIS_STRONG,
        data_certain=False,  # Stale or malformed data
    )
    res = engine.evaluate_with_evidence(pos, ev, "2026-08-14T03:50:00+00:00")
    assert res.action == LifecycleAction.HOLD.value
    assert OverlayState.DATA_UNCERTAINTY in engine.overlays
    assert engine.current_horizon is HorizonState.IMPULSE


def test_orthogonal_protection_update():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.TACTICAL)
    pos = make_position()

    # Move from P0 to P2 PROFIT_PROTECTED
    ev = LifecycleEvidence(
        suggested_protection=ProtectionState.P2_PROFIT_PROTECTED,
        persistence_evidence_valid=False,
    )
    res = engine.evaluate_with_evidence(pos, ev, "2026-08-14T04:00:00+00:00")
    assert res.action == LifecycleAction.UPDATE_PROTECTION.value
    assert engine.protection_state is ProtectionState.P2_PROFIT_PROTECTED
    assert engine.current_horizon is HorizonState.TACTICAL  # Horizon unchanged
    assert engine.thesis_state is ThesisState.THESIS_VALID  # Thesis unchanged


def test_emergency_override():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.SESSION_TREND)
    pos = make_position()

    ev = LifecycleEvidence(is_emergency=True)
    res = engine.evaluate_with_evidence(pos, ev, "2026-08-14T04:05:00+00:00")
    assert res.action == LifecycleAction.EXIT_EMERGENCY.value
    assert res.lifecycle_state == "FLAT"
    assert engine.is_active is False


def test_e2e_protocol_conformance():
    engine = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
    pos = make_position()
    event = CanonicalMarketEvent(
        record_id="rec-1",
        event_type="trade",
        instrument_id="NIFTY-CE",
        event_time="2026-08-14T03:45:00+00:00",
        available_at="2026-08-14T03:45:00+00:00",
        source="truedata",
        source_version="v1",
        payload={"price": 100.0},
    )

    eval_result = engine.evaluate(pos, event)
    assert eval_result.position_id == "pos-1"
    assert eval_result.action == "HOLD"
