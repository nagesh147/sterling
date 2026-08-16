"""MICRO/SCALP/EXTENDED_SCALP/INTRADAY: graph, hysteresis, no single-variable promote."""
from __future__ import annotations

from app.engines.adaptive_edge.contracts import AdaptiveEdgeState, RiskAuthorization, RiskState
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.lifecycle_engine import HorizonState
from app.engines.adaptive_edge.opportunity_mode import (
    ALLOWED_EDGES,
    MODE_TO_HORIZON,
    ModeEvidence,
    ModePolicy,
    OpportunityMode,
    OpportunityModeEngine,
    propose_mode,
    research_mode_policy,
)
from app.engines.adaptive_edge.state import StateEvent, transition


def _ev(**overrides) -> ModeEvidence:
    base = dict(
        score_aligned=True,
        features_valid=True,
        data_certain=True,
        favorable_points=0.0,
        giveback_ratio=0.0,
        minutes_to_cutoff=180.0,
        holding_age_seconds=600.0,
    )
    base.update(overrides)
    return ModeEvidence(**base)


def test_canonical_modes_and_horizon_map():
    assert [mode.value for mode in OpportunityMode] == [
        "MICRO",
        "SCALP",
        "EXTENDED_SCALP",
        "INTRADAY",
    ]
    assert MODE_TO_HORIZON[OpportunityMode.MICRO] is HorizonState.IMPULSE
    assert MODE_TO_HORIZON[OpportunityMode.SCALP] is HorizonState.TACTICAL
    assert MODE_TO_HORIZON[OpportunityMode.EXTENDED_SCALP] is HorizonState.INTRADAY_SWING
    assert MODE_TO_HORIZON[OpportunityMode.INTRADAY] is HorizonState.SESSION_TREND
    assert (OpportunityMode.MICRO, OpportunityMode.INTRADAY) in ALLOWED_EDGES


def test_price_alone_does_not_propose_scalp():
    policy = research_mode_policy()
    assert propose_mode(_ev(favorable_points=80.0, score_aligned=False), policy) is OpportunityMode.MICRO
    assert propose_mode(_ev(favorable_points=80.0, features_valid=False), policy) is OpportunityMode.MICRO


def test_elapsed_time_alone_does_not_propose_intraday():
    policy = research_mode_policy()
    assert (
        propose_mode(_ev(favorable_points=0.0, holding_age_seconds=10_000.0), policy)
        is OpportunityMode.MICRO
    )


def test_hysteresis_blocks_one_bar_flicker():
    engine = OpportunityModeEngine(ModePolicy("T", persistence_bars=3), started_at="t0")
    first = engine.update(_ev(favorable_points=8.0), timestamp="t1")
    assert first.mode is OpportunityMode.MICRO
    assert first.transitioned is False
    engine.update(_ev(favorable_points=8.0), timestamp="t2")
    third = engine.update(_ev(favorable_points=8.0), timestamp="t3")
    assert third.mode is OpportunityMode.SCALP
    assert third.promoted is True


def test_ladder_and_giveback_downgrade():
    policy = ModePolicy("T", persistence_bars=1)
    engine = OpportunityModeEngine(policy, started_at="t0")
    assert engine.update(_ev(favorable_points=6.0), timestamp="t1").mode is OpportunityMode.SCALP
    assert engine.update(_ev(favorable_points=16.0), timestamp="t2").mode is OpportunityMode.EXTENDED_SCALP
    intra = engine.update(_ev(favorable_points=30.0), timestamp="t3")
    assert intra.mode is OpportunityMode.INTRADAY
    down = engine.update(_ev(favorable_points=30.0, giveback_ratio=0.9), timestamp="t4")
    assert down.mode is OpportunityMode.MICRO
    assert down.downgraded is True


def test_mode_transition_does_not_change_authorized_risk():
    auth = RiskAuthorization(
        opportunity_id="o",
        authorized_risk=10.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="p",
        issued_at="t0",
    )
    state = AdaptiveEdgeState(authorization=auth)
    moved = transition(state, StateEvent.ENTER_INTRADAY).resulting_state
    assert moved.authorization is auth
    assert moved.authorization.authorized_risk == 10.0
    assert FORMULAS["F-104"].status is FormulaStatus.IMPLEMENTED
    assert FORMULAS["F-106"].status is FormulaStatus.IMPLEMENTED


def test_session_records_mode_ladder():
    from datetime import datetime, timedelta, timezone

    from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
    from app.engines.adaptive_edge.f101 import trial_identity_parameters
    from app.engines.adaptive_edge.research_e2e import run_research_session

    def bar(ts: str, record_id: str, close: float) -> CanonicalMarketEvent:
        return CanonicalMarketEvent(
            record_id=record_id,
            event_type="bar",
            instrument_id="NIFTY-I",
            event_time=ts,
            available_at=ts,
            source="truedata",
            source_version="2.6",
            payload={"open": close, "high": close, "low": close, "close": close, "volume": 1.0, "oi": 1.0},
        )

    def tick(ts: str, seq: int, close: float) -> CanonicalMarketEvent:
        return CanonicalMarketEvent(
            record_id=f"T{seq}",
            event_type="tick",
            instrument_id="NIFTY-I",
            event_time=ts,
            available_at=ts,
            source="truedata",
            source_version="2.6",
            sequence=seq,
            payload={
                "ltp": close,
                "volume": 1.0,
                "oi": 1.0,
                "bid": close,
                "bidqty": 80.0,
                "ask": close,
                "askqty": 20.0,
            },
        )

    start = datetime(2026, 8, 13, 3, 45, tzinfo=timezone.utc)
    bars = []
    ticks = []
    for i in range(24):
        ts = (start + timedelta(minutes=i)).isoformat()
        close = 100.0 + i
        bars.append(bar(ts, f"B{i}", close))
        ticks.append(tick(ts, i, close))
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
        mode_policy=ModePolicy("T", persistence_bars=2, scalp_favorable_points=2.0, extended_favorable_points=5.0, intraday_favorable_points=8.0),
    )
    assert session.entries == 1
    assert session.last_mode in {"SCALP", "EXTENDED_SCALP", "INTRADAY"}
    assert session.mode_transitions
    assert session.legs[0].entry_mode == "MICRO"
    assert session.legs[0].peak_mode != "MICRO"
    assert FORMULAS["F-104"].status is FormulaStatus.IMPLEMENTED
