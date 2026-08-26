from __future__ import annotations

from app.engines.adaptive_edge.lifecycle_engine import (
    A126LifecycleEngine,
    HorizonState,
    LifecycleAction,
    LifecycleEvidence,
)
from app.engines.adaptive_edge.e2e import PositionState


def position() -> PositionState:
    return PositionState(
        position_id="pos-1",
        instrument_id="NIFTY26AUG24500CE",
        quantity=25,
        average_price=100.0,
        lifecycle_state="OPEN",
        source_execution_event_id="evt-1",
    )


def test_f113_session_cutoff_forces_flatten() -> None:
    engine = A126LifecycleEngine("pos-1", HorizonState.SESSION_TREND)
    result = engine.evaluate_with_evidence(
        position(),
        LifecycleEvidence(session_cutoff_reached=True),
        "2026-08-17T14:45:00+05:30",
    )
    assert result.action == LifecycleAction.EXIT_SESSION_CUTOFF.value
    assert engine.is_active is False


def test_f113_hard_risk_breach_overrides_horizon() -> None:
    engine = A126LifecycleEngine("pos-1", HorizonState.SESSION_EXTENSION)
    result = engine.evaluate_with_evidence(
        position(),
        LifecycleEvidence(hard_risk_breached=True),
        "2026-08-17T11:00:00+05:30",
    )
    assert result.action == LifecycleAction.EXIT_HARD_STOP.value
    assert engine.is_active is False


def test_f113_thesis_invalidates_position() -> None:
    engine = A126LifecycleEngine("pos-1")
    result = engine.evaluate_with_evidence(
        position(),
        LifecycleEvidence(thesis_valid=False),
        "2026-08-17T10:00:00+05:30",
    )
    assert result.action == LifecycleAction.EXIT_THESIS_INVALID.value
    assert engine.is_active is False
