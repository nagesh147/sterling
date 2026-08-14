"""A177 protection: explicit policy only. F-112 stays LOCKED."""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.lifecycle_engine import (
    A126LifecycleEngine,
    LifecycleAction,
    LifecycleEvidence,
)
from app.engines.adaptive_edge.protection import ProtectionEngine, ProtectionPolicy
from app.engines.adaptive_edge.e2e import PositionState


def test_buy_protective_stop_fires_below_entry():
    engine = ProtectionEngine(
        ProtectionPolicy("EXAMPLE", protective_stop_points=10.0),
        side="BUY",
        entry_price=100.0,
    )
    hold = engine.update(99.0)
    assert hold.hit is False
    fire = engine.update(90.0)
    assert fire.hit is True
    assert fire.authority == "PROTECTIVE_STOP"
    assert fire.stop_price == 90.0


def test_sell_protective_stop_fires_above_entry():
    engine = ProtectionEngine(
        ProtectionPolicy("EXAMPLE", protective_stop_points=10.0),
        side="SELL",
        entry_price=100.0,
    )
    assert engine.update(105.0).hit is False
    fire = engine.update(110.0)
    assert fire.authority == "PROTECTIVE_STOP"


def test_trail_tightens_and_never_loosens_for_buy():
    engine = ProtectionEngine(
        ProtectionPolicy("EXAMPLE", trail_points=5.0),
        side="BUY",
        entry_price=100.0,
    )
    up = engine.update(110.0)
    assert up.trail_price == 105.0
    assert up.extreme == 110.0
    pullback = engine.update(107.0)
    assert pullback.extreme == 110.0
    assert pullback.trail_price == 105.0
    assert pullback.hit is False
    hit = engine.update(105.0)
    assert hit.authority == "TRAILING_PROTECTION"


def test_profit_lock_activates_only_after_threshold():
    engine = ProtectionEngine(
        ProtectionPolicy(
            "EXAMPLE",
            profit_lock_activation_points=20.0,
            profit_lock_offset_points=5.0,
        ),
        side="BUY",
        entry_price=100.0,
    )
    early = engine.update(110.0)
    assert early.lock_active is False
    assert early.lock_price is None
    armed = engine.update(120.0)
    assert armed.lock_active is True
    assert armed.lock_price == 115.0
    fire = engine.update(115.0)
    assert fire.authority == "PROFIT_LOCK"


def test_session_cutoff_wins_over_stop():
    pos = PositionState("p", "NIFTY-I", 1, 100.0, "OPEN", "e1")
    engine = A126LifecycleEngine("p")
    result = engine.evaluate_with_evidence(
        pos,
        LifecycleEvidence(session_cutoff_reached=True, protective_stop_hit=True),
        "2026-08-13T09:15:00+00:00",
    )
    assert result.action == LifecycleAction.EXIT_SESSION_CUTOFF.value


def test_lifecycle_emits_protection_exits():
    pos = PositionState("p", "NIFTY-I", 1, 100.0, "OPEN", "e1")
    stop = A126LifecycleEngine("p").evaluate_with_evidence(
        pos,
        LifecycleEvidence(protective_stop_hit=True),
        "2026-08-13T04:00:00+00:00",
    )
    assert stop.action == LifecycleAction.EXIT_HARD_STOP.value
    trail = A126LifecycleEngine("p2").evaluate_with_evidence(
        pos,
        LifecycleEvidence(trailing_hit=True),
        "2026-08-13T04:01:00+00:00",
    )
    assert trail.action == LifecycleAction.EXIT_PROFIT_PROTECTION.value
    assert FORMULAS["F-112"].status is FormulaStatus.LOCKED


def test_policy_rejects_non_positive_distance():
    with pytest.raises(ValueError):
        ProtectionPolicy("BAD", protective_stop_points=0.0)


def test_session_stop_flattens_before_cutoff():
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
    for i in range(16):
        ts = (start + timedelta(minutes=i)).isoformat()
        close = 100.0 + i if i < 15 else 80.0
        bars.append(bar(ts, f"B{i}", close))
        ticks.append(tick(ts, i, close))
    session = run_research_session(
        symbol="NIFTY-I",
        bar_events=bars,
        tick_events=ticks,
        params=trial_identity_parameters(w_short=5, w_long=10),
        bar_sequence_hash="bar",
        tick_sequence_hash="tick",
        protection_policy=ProtectionPolicy("EXAMPLE", protective_stop_points=5.0),
    )
    assert session.exits == 1
    assert "protection_exit" in session.audit_stages
    assert session.last_position_quantity == 0
    assert session.software_complete is True
    assert FORMULAS["F-111"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-112"].status is FormulaStatus.LOCKED


def test_production_readiness_stays_blocked_for_live():
    from app.engines.adaptive_edge.production_readiness import production_readiness

    board = {item.name: item for item in production_readiness()}
    assert board["execution_gate_blocked"].ready is True
    assert board["a197_dataset"].ready is False
    assert board["parameter_freeze"].ready is False
    assert board["formula_registry_locked"].ready is True
