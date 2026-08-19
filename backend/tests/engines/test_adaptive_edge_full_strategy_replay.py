"""Full Adaptive Edge A→K replay on the composed execution path.

Same provider sequence + same ReplayContext + same simulated broker
must produce an identical TraceHash across decision, risk, instrument,
order, execution, position, lifecycle, PnL, and audit.

This is research/simulation replay. Production remains BLOCKED.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.e2e import ReplayContext
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_gate import ExecutionGateStatus
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.protection import ProtectionPolicy
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.engines.adaptive_edge.entry_decision import EntryDecisionEvidence
from app.engines.adaptive_edge.instrument_selection import ListedOptionCandidate
from app.engines.adaptive_edge.strategy_pipeline import StrategyConfig
from app.engines.adaptive_edge.strategy_replay import run_full_strategy_replay


def _bar(i: int, close: float, *, trend_step: float = 8.0) -> CanonicalMarketEvent:
    total_mins = 45 + i
    hour = 3 + total_mins // 60
    minute = total_mins % 60
    ts = f"2026-08-17T{hour:02d}:{minute:02d}:00+00:00"
    open_px = close - trend_step
    return CanonicalMarketEvent(
        record_id=f"BAR-{i:03d}",
        event_type="bar",
        instrument_id="NIFTY-I",
        event_time=ts,
        available_at=ts,
        source="truedata",
        source_version="2.6",
        sequence=i,
        payload={
            "open": open_px,
            "high": max(open_px, close) + 2.0,
            "low": min(open_px, close) - 2.0,
            "close": close,
            "volume": 1500.0 + i * 50.0,
            "oi": 100000.0 + i * 200.0,
        },
        provenance={"provider": "TrueData", "feed": "replay"},
    )


def _tick(i: int, ltp: float) -> CanonicalMarketEvent:
    total_mins = 45 + (i // 2)
    hour = 3 + total_mins // 60
    minute = total_mins % 60
    second = (i % 2) * 30
    ts = f"2026-08-17T{hour:02d}:{minute:02d}:{second:02d}+00:00"
    return CanonicalMarketEvent(
        record_id=f"TICK-{i:03d}",
        event_type="tick",
        instrument_id="NIFTY-I",
        event_time=ts,
        available_at=ts,
        source="truedata",
        source_version="2.6",
        sequence=i,
        payload={
            "ltp": ltp,
            "volume": 50.0,
            "oi": 100000.0,
            "bid": ltp - 0.25,
            "ask": ltp + 0.25,
            "bidqty": 200.0,
            "askqty": 100.0,
        },
    )


def _bull_then_giveback(n: int = 24) -> tuple[list[CanonicalMarketEvent], list[CanonicalMarketEvent]]:
    bars: list[CanonicalMarketEvent] = []
    ticks: list[CanonicalMarketEvent] = []
    price = 24500.0
    for i in range(n):
        if i < 16:
            price += 8.0
        else:
            price -= 20.0
        bars.append(_bar(i, price))
        ticks.append(_tick(i, price))
        ticks.append(_tick(n + i, price + 1.0))
    return bars, ticks


def _ctx(seed: int = 7) -> ReplayContext:
    return ReplayContext(
        decision_time="2026-08-17T03:45:00+00:00",
        event_time="2026-08-17T03:45:00+00:00",
        deterministic_id_namespace="full-ak-replay",
        sequence_seed=seed,
        broker_simulation_seed=seed,
    )


def _config() -> StrategyConfig:
    return StrategyConfig(
        symbol="NIFTY-I",
        authorized_risk=5000.0,
        execution_cost=20.0,
        min_net_value=10.0,
        option_moneyness="ATM",
        stop_points=30.0,
    )


def _policy() -> ProtectionPolicy:
    return ProtectionPolicy(
        "REPLAY_NOT_LIVE",
        protective_stop_points=10.0,
        trail_points=5.0,
        profit_lock_activation_points=20.0,
        profit_lock_offset_points=5.0,
    )


def _run(bars, ticks, *, seed: int = 7, formula_ids=("F-004",), **kwargs):
    return run_full_strategy_replay(
        bars,
        ticks,
        replay_context=_ctx(seed),
        config=_config(),
        protection_policy=_policy(),
        formula_ids=formula_ids,
        entry_fill_price=150.0,
        **kwargs,
    )


def test_same_input_and_replay_context_produce_identical_trace_hash():
    bars, ticks = _bull_then_giveback()
    a = _run(bars, ticks)
    b = _run(bars, ticks)

    assert a.traded is True
    assert a.trace_hash == b.trace_hash
    assert a.sequence_hash == b.sequence_hash
    assert a.audit == b.audit
    assert a.decision.direction == b.decision.direction
    assert a.decision.horizon == b.decision.horizon
    assert a.sizing.final_quantity == b.sizing.final_quantity
    assert a.order.order_intent_id == b.order.order_intent_id
    assert a.order.fingerprint() == b.order.fingerprint()
    assert a.entry_execution.execution_event_id == b.entry_execution.execution_event_id
    assert a.initial_position.quantity == b.initial_position.quantity
    assert a.final_position.quantity == b.final_position.quantity
    assert a.lifecycle_actions == b.lifecycle_actions
    assert a.realized_pnl == b.realized_pnl
    assert a.submissions == b.submissions


def test_shuffled_provider_arrival_does_not_change_trace_hash():
    bars, ticks = _bull_then_giveback()
    reversed_bars = list(reversed(bars))
    a = _run(bars, ticks)
    b = _run(reversed_bars, ticks)
    assert CanonicalEventSequence.from_events(bars).sequence_hash == (
        CanonicalEventSequence.from_events(reversed_bars).sequence_hash
    )
    assert a.trace_hash == b.trace_hash
    assert a.sequence_hash == b.sequence_hash


def test_different_replay_seed_changes_order_identity_and_hash():
    bars, ticks = _bull_then_giveback()
    a = _run(bars, ticks, seed=7)
    b = _run(bars, ticks, seed=99)
    assert a.sequence_hash == b.sequence_hash
    assert a.order.order_intent_id != b.order.order_intent_id
    assert a.trace_hash != b.trace_hash


def test_full_path_covers_required_ak_stages():
    bars, ticks = _bull_then_giveback()
    result = _run(bars, ticks)
    stages = [record.stage for record in result.audit]
    for required in (
        "market_sequence",
        "feature_snapshot",
        "decision",
        "edge",
        "economics",
        "risk_authorization",
        "instrument",
        "order_intent",
        "execution_event",
        "position",
        "lifecycle",
        "pnl",
    ):
        assert required in stages
    assert result.decision is not None
    assert result.horizon == result.decision.horizon.value
    assert result.order is not None
    assert result.entry_execution is not None
    assert result.initial_position is not None
    assert result.final_position is not None
    assert result.final_position.quantity == 0
    assert result.lifecycle_actions
    assert result.exit_execution is not None
    assert result.submissions == 2


def test_production_replay_is_blocked_with_zero_submissions_and_stable_hash():
    bars, ticks = _bull_then_giveback()
    a = _run(bars, ticks, formula_ids=None)
    b = _run(bars, ticks, formula_ids=None)
    assert a.execution_gate.status is ExecutionGateStatus.BLOCKED
    assert a.production_gate_authorized is False
    assert a.traded is False
    assert a.order is None
    assert a.submissions == 0
    assert a.trace_hash == b.trace_hash
    assert FORMULAS["F-111"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-112"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED


def test_required_listed_chain_fails_closed_when_empty():
    bars, ticks = _bull_then_giveback()
    result = _run(bars, ticks, require_listed_chain=True)
    assert result.traded is False
    assert result.order is None
    assert result.submissions == 0
    assert result.exit_reason is not None and "LISTED_CHAIN" in result.exit_reason


def test_listed_chain_selects_highest_ev_and_is_deterministic():
    bars, ticks = _bull_then_giveback()
    chain = (
        ListedOptionCandidate(
            instrument_id="NIFTY26AUG24600CE",
            option_type="CE",
            strike=24600.0,
            expiry="2026-08-27",
            expected_net_value=40.0,
            available_at="2026-08-17T03:45:00+00:00",
        ),
        ListedOptionCandidate(
            instrument_id="NIFTY26AUG24500CE",
            option_type="CE",
            strike=24500.0,
            expiry="2026-08-27",
            expected_net_value=95.0,
            available_at="2026-08-17T03:45:00+00:00",
        ),
        ListedOptionCandidate(
            instrument_id="NIFTY26AUG24500PE",
            option_type="PE",
            strike=24500.0,
            expiry="2026-08-27",
            expected_net_value=200.0,
            available_at="2026-08-17T03:45:00+00:00",
        ),
    )
    a = _run(bars, ticks, listed_candidates=chain)
    b = _run(bars, ticks, listed_candidates=chain)
    assert a.traded is True
    assert a.instrument_id == "NIFTY26AUG24500CE"
    assert a.trace_hash == b.trace_hash
    assert a.instrument_id == b.instrument_id


def test_f110_missing_conservative_ev_blocks_replay_without_inventing_q():
    bars, ticks = _bull_then_giveback()
    result = _run(
        bars,
        ticks,
        entry_evidence=EntryDecisionEvidence(
            option_type="CE",
            conservative_ev=None,
            directional_edge_ok=True,
            liquidity_ok=True,
            slippage_ok=True,
            risk_ok=True,
        ),
    )
    assert result.traded is False
    assert result.submissions == 0
    assert result.exit_reason == "missing_conservative_ev"


def test_f110_on_replay_snapshots_fails_closed_when_features_are_missing():
    bars, ticks = _bull_then_giveback()
    evidence = EntryDecisionEvidence(
        option_type="CE",
        conservative_ev=40.0,
        directional_edge_ok=True,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    a = _run(bars, ticks, entry_evidence=evidence)
    b = _run(bars, ticks, entry_evidence=evidence)
    assert a.traded is False
    assert a.exit_reason == "entry_conjunction_failed:DataOK"
    assert a.trace_hash == b.trace_hash
    assert a.submissions == 0
