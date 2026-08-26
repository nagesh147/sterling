"""Thesis, overlays, P0-P3, H4, operating posture. F-105/F-106 stay LOCKED."""
from __future__ import annotations

from app.engines.adaptive_edge.contracts import DynamicMode
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.lifecycle_engine import (
    OverlayState,
    ProtectionState,
    ThesisState,
)
from app.engines.adaptive_edge.management import (
    classify_operating_mode,
    classify_overlays,
    classify_protection_stage,
    classify_thesis,
    research_management_policy,
    want_session_extension,
)
from app.engines.adaptive_edge.opportunity_mode import OpportunityMode
from app.engines.adaptive_edge.protection import ProtectionDecision, ProtectionEngine, ProtectionPolicy


def test_thesis_invalid_requires_persistence():
    policy = research_management_policy()
    assert (
        classify_thesis(
            score_aligned=False,
            features_valid=True,
            giveback_ratio=0.0,
            favorable_points=0.0,
            misaligned_streak=1,
            policy=policy,
        )
        is ThesisState.THESIS_WEAKENING
    )
    assert (
        classify_thesis(
            score_aligned=False,
            features_valid=True,
            giveback_ratio=0.0,
            favorable_points=0.0,
            misaligned_streak=15,
            policy=policy,
        )
        is ThesisState.THESIS_INVALID
    )


def test_overlays_and_h4():
    policy = research_management_policy()
    overlays = classify_overlays(
        features_valid=False,
        li_valid=False,
        giveback_ratio=0.99,
        peak_favorable_points=25.0,
        volatility_ratio=3.0,
        structure=None,
        side=None,
        policy=policy,
    )
    assert OverlayState.DATA_UNCERTAINTY in overlays
    assert OverlayState.LIQUIDITY_STRESS in overlays
    assert OverlayState.ECONOMIC_COLLAPSE in overlays
    assert OverlayState.BURST in overlays
    assert want_session_extension(
        mode=OpportunityMode.INTRADAY,
        minutes_to_cutoff=60.0,
        favorable_points=20.0,
        score_aligned=True,
        policy=policy,
    )
    assert not want_session_extension(
        mode=OpportunityMode.MICRO,
        minutes_to_cutoff=60.0,
        favorable_points=20.0,
        score_aligned=True,
        policy=policy,
    )


def test_protection_stages_walk_p0_to_p2():
    engine = ProtectionEngine(
        ProtectionPolicy(
            "EX",
            protective_stop_points=10.0,
            trail_points=5.0,
            profit_lock_activation_points=20.0,
            profit_lock_offset_points=5.0,
        ),
        side="BUY",
        entry_price=100.0,
    )
    p0 = classify_protection_stage(
        favorable_points=0.0, protection=engine.update(99.0), stop_points=10.0
    )
    assert p0 is ProtectionState.P0_RISK_CONTROLLED
    p1 = classify_protection_stage(
        favorable_points=8.0, protection=engine.update(108.0), stop_points=10.0
    )
    assert p1 is ProtectionState.P1_BREAKEVEN_PROTECTED
    armed = engine.update(120.0)
    assert armed.lock_active is True
    p2 = classify_protection_stage(
        favorable_points=20.0, protection=armed, stop_points=10.0
    )
    assert p2 in {ProtectionState.P2_PROFIT_PROTECTED, ProtectionState.P3_AGGRESSIVE_TRAIL}


def test_operating_mode_posture():
    assert (
        classify_operating_mode(
            in_position=False,
            cutoff=False,
            thesis=ThesisState.THESIS_VALID,
            opportunity_mode=None,
            overlays=(),
        )
        is DynamicMode.OBSERVE
    )
    assert (
        classify_operating_mode(
            in_position=True,
            cutoff=True,
            thesis=ThesisState.THESIS_VALID,
            opportunity_mode=OpportunityMode.INTRADAY,
            overlays=(),
        )
        is DynamicMode.EXIT_ONLY
    )
    assert (
        classify_operating_mode(
            in_position=True,
            cutoff=False,
            thesis=ThesisState.THESIS_WEAKENING,
            opportunity_mode=OpportunityMode.SCALP,
            overlays=(),
        )
        is DynamicMode.DEFENSIVE
    )
    assert FORMULAS["F-105"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-106"].status is FormulaStatus.LOCKED


def test_session_records_management_states():
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
        management_policy=research_management_policy(),
    )
    assert session.entries == 1
    assert session.last_thesis in {
        "THESIS_STRONG",
        "THESIS_VALID",
        "THESIS_WEAKENING",
        "THESIS_INVALID",
    }
    assert session.last_protection_stage in {
        "P0_RISK_CONTROLLED",
        "P1_BREAKEVEN_PROTECTED",
        "P2_PROFIT_PROTECTED",
        "P3_AGGRESSIVE_TRAIL",
    }
    assert session.last_operating_mode in {
        "observe",
        "active",
        "intraday",
        "defensive",
        "exit_only",
        "halted",
    }
    assert session.last_horizon is not None
    assert session.software_complete is True
