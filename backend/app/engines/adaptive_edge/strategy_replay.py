"""Full Adaptive Edge A→K replay on the composed execution path.

Composes existing research/simulation boundaries. Does not invent F-101..F-114
mathematics, does not unlock formulas, and does not submit in production.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

from .accounting import AccountingSnapshot, mark_accounting, reconcile_realized_pnl
from .broker_event_mapper import BrokerExecutionEvent
from .contracts import RiskAuthorization, RiskState
from .e2e import (
    AuditLedger,
    AuditRecord,
    PositionState,
    PredictionEvidence,
    ReplayContext,
    SelectedInstrument,
)
from .entry_decision import EntryDecisionEvidence, evaluate_entry_decision
from .economic import EconomicAssessment, evaluate_economics
from .edge import EdgeAssessment
from .event_boundary import CanonicalMarketEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent
from .execution_gate import (
    REQUIRED_STRATEGY_FORMULAS,
    ExecutionGateDecision,
    evaluate_execution_gate,
)
from .execution_path import AdaptiveEdgeExecutionPath
from .instrument_selection import (
    InstrumentSelectionError,
    ListedOptionCandidate,
    select_listed_instrument,
)
from .position_lifecycle import ManagedPosition
from .protection import ProtectionPolicy
from .replay import CanonicalEventSequence
from .risk_sizing import (
    ExecutionCostParameters,
    PositionSizingAssessment,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)
from .strategy_pipeline import (
    MarketStateDecision,
    SimulatedExecutionTransport,
    StrategyConfig,
    _make_param_metadata,
    build_causal_feature_snapshots,
    evaluate_market_decision,
    select_option_contract,
)
from .structure import build_structure_series


@dataclass(frozen=True)
class FullStrategyReplayTrace:
    sequence_hash: str
    execution_gate: ExecutionGateDecision
    decision: MarketStateDecision | None
    horizon: str | None
    sizing: PositionSizingAssessment | None
    instrument_id: str | None
    order: CanonicalOrderIntent | None
    entry_execution: CanonicalExecutionEvent | None
    exit_execution: CanonicalExecutionEvent | None
    initial_position: PositionState | None
    final_position: PositionState | None
    lifecycle_actions: tuple[str, ...]
    protection_authorities: tuple[str, ...]
    realized_pnl: float
    accounting: AccountingSnapshot | None
    submissions: int
    audit: tuple[AuditRecord, ...]
    production_gate_authorized: bool
    traded: bool
    exit_reason: str | None

    @property
    def trace_hash(self) -> str:
        payload = {
            "sequence_hash": self.sequence_hash,
            "gate": self.execution_gate.status.value,
            "blocking": list(self.execution_gate.blocking_formulas),
            "direction": None if self.decision is None else self.decision.direction,
            "horizon": self.horizon,
            "decision_reason": None if self.decision is None else self.decision.decision_reason,
            "quantity": None if self.sizing is None else self.sizing.final_quantity,
            "instrument_id": self.instrument_id,
            "order_intent_id": None if self.order is None else self.order.order_intent_id,
            "order_fingerprint": None if self.order is None else self.order.fingerprint(),
            "entry_execution_id": None
            if self.entry_execution is None
            else self.entry_execution.execution_event_id,
            "exit_execution_id": None
            if self.exit_execution is None
            else self.exit_execution.execution_event_id,
            "entry_qty": None if self.initial_position is None else self.initial_position.quantity,
            "final_qty": None if self.final_position is None else self.final_position.quantity,
            "lifecycle_actions": list(self.lifecycle_actions),
            "protection_authorities": list(self.protection_authorities),
            "realized_pnl": self.realized_pnl,
            "traded": self.traded,
            "exit_reason": self.exit_reason,
            "audit": [
                (record.sequence, record.stage, record.object_id, record.parent_ids)
                for record in self.audit
            ],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def run_full_strategy_replay(
    bar_events: Sequence[CanonicalMarketEvent],
    tick_events: Sequence[CanonicalMarketEvent] = (),
    *,
    replay_context: ReplayContext,
    config: StrategyConfig = StrategyConfig(),
    protection_policy: ProtectionPolicy | None = None,
    formula_ids: tuple[str, ...] | None = ("F-004",),
    entry_fill_price: float = 150.0,
    listed_candidates: Sequence[ListedOptionCandidate] = (),
    require_listed_chain: bool = False,
    entry_evidence: EntryDecisionEvidence | None = None,
) -> FullStrategyReplayTrace:
    """Replay one market sequence through the composed Adaptive Edge path."""
    if not bar_events:
        raise ValueError("market event sequence cannot be empty")

    sequence = CanonicalEventSequence.from_events(bar_events)
    bars = sequence.events
    audit = AuditLedger()
    audit.append("market_sequence", sequence.sequence_hash)

    required = REQUIRED_STRATEGY_FORMULAS if formula_ids is None else formula_ids
    gate = evaluate_execution_gate(required)
    transport = SimulatedExecutionTransport()

    snapshots = build_causal_feature_snapshots(
        bars,
        tick_events,
        symbol=config.symbol,
        strategy_version=config.strategy_version,
        feature_set_version=config.feature_set_version,
        tick_size=config.tick_size,
        value_area_coverage=config.value_area_coverage,
    )
    structures = build_structure_series(
        bars,
        tick_events,
        tick_size=config.tick_size,
        value_area_coverage=config.value_area_coverage,
    )
    if snapshots:
        audit.append("feature_snapshot", snapshots[0].snapshot_id, sequence.sequence_hash)

    if not gate.authorized:
        return _blocked(sequence.sequence_hash, gate, audit, transport)

    trigger_index = -1
    decision: MarketStateDecision | None = None
    for idx, (snap, struct) in enumerate(zip(snapshots, structures)):
        candidate = evaluate_market_decision(snap, struct, idx, config)
        if candidate.direction != "NEUTRAL":
            trigger_index = idx
            decision = candidate
            break
    if decision is None or trigger_index < 0:
        return _blocked(
            sequence.sequence_hash,
            gate,
            audit,
            transport,
            traded=False,
            exit_reason="NO_DIRECTIONAL_OPPORTUNITY",
        )

    trigger_snap = snapshots[trigger_index]
    trigger_struct = structures[trigger_index]
    audit.append("decision", f"DEC-{trigger_snap.snapshot_id}", trigger_snap.snapshot_id)

    opp_id = replay_context.deterministic_id("OPP", trigger_snap.snapshot_id)
    expected_gross = decision.target_points * 2.0
    edge = EdgeAssessment(
        opportunity_id=opp_id,
        score=0.75,
        confidence=1.0 - decision.uncertainty,
        expected_gross_value=expected_gross,
        formula_id="F-004",
        formula_version="1.0",
        inputs={"target_points": decision.target_points, "stop_points": decision.stop_points},
    )
    audit.append("edge", edge.opportunity_id, f"DEC-{trigger_snap.snapshot_id}")
    economics: EconomicAssessment = evaluate_economics(
        edge,
        execution_cost=config.execution_cost,
        minimum_net_value=config.min_net_value,
    )
    audit.append("economics", f"ECON-{opp_id}", edge.opportunity_id)
    if not economics.eligible:
        return _blocked(
            sequence.sequence_hash,
            gate,
            audit,
            transport,
            decision=decision,
            exit_reason="INSUFFICIENT_ECONOMIC_EDGE",
        )

    if entry_evidence is not None:
        prediction = PredictionEvidence(
            prediction_id=replay_context.deterministic_id("PRED", trigger_snap.snapshot_id),
            snapshot_id=trigger_snap.snapshot_id,
            opportunity_id=opp_id,
            strategy_version=config.strategy_version,
            model_version="replay-v1",
            prediction_time=trigger_snap.decision_time,
            target_definition_version="target-v1",
            horizon_definition_version=decision.horizon.value,
            prediction_type="DIRECTION",
            prediction_value=decision.target_points,
            uncertainty=decision.uncertainty,
            calibration_reference=None,
            provenance={"stage": "f110"},
        )
        f110 = evaluate_entry_decision(
            trigger_snap, prediction, edge, economics, entry_evidence
        )
        audit.append("entry_decision", f110.action.value, prediction.prediction_id)
        if not f110.eligible:
            return _blocked(
                sequence.sequence_hash,
                gate,
                audit,
                transport,
                decision=decision,
                exit_reason=f110.reason,
            )

    spot_close = trigger_struct.close or 24500.0
    initial_stop_price = (
        spot_close - decision.stop_points
        if decision.direction == "BULLISH"
        else spot_close + decision.stop_points
    )
    cost_params = ExecutionCostParameters(
        spread_cost=_make_param_metadata("spread_cost", 0.5),
        expected_slippage=_make_param_metadata("expected_slippage", 0.5),
        brokerage_per_unit=_make_param_metadata("brokerage_per_unit", 0.2),
        exchange_charges_per_unit=_make_param_metadata("exchange_charges_per_unit", 0.1),
        taxes_per_unit=_make_param_metadata("taxes_per_unit", 0.1),
        latency_cost_per_unit=_make_param_metadata("latency_cost_per_unit", 0.1),
    )
    risk_unit = calculate_risk_per_unit(
        entry_price=spot_close,
        initial_stop=initial_stop_price,
        cost_params=cost_params,
    )
    risk_auth = RiskAuthorization(
        opportunity_id=opp_id,
        authorized_risk=config.authorized_risk,
        risk_state=RiskState.AUTHORIZED,
        policy_version="replay-v1",
        issued_at=trigger_snap.decision_time,
    )
    sizing = calculate_position_sizing(
        risk_auth,
        risk_unit,
        SizingParameters(
            max_position_qty=_make_param_metadata("max_position_qty", float(config.max_quantity), units="units"),
            max_capital_allocation=_make_param_metadata("max_capital_allocation", 50_000_000.0, units="INR"),
            lot_size=_make_param_metadata("lot_size", 25.0, units="units"),
        ),
    )
    audit.append("risk_authorization", f"AUTH-{opp_id}", opp_id)
    if not sizing.valid or sizing.final_quantity <= 0:
        return _blocked(
            sequence.sequence_hash,
            gate,
            audit,
            transport,
            decision=decision,
            sizing=sizing,
            exit_reason="ZERO_AUTHORIZED_QUANTITY",
        )

    option_type = "CE" if decision.direction == "BULLISH" else "PE"
    if require_listed_chain or listed_candidates:
        try:
            listed = select_listed_instrument(
                listed_candidates,
                decision_time=trigger_snap.decision_time,
                option_type=option_type,
            )
        except InstrumentSelectionError as exc:
            return _blocked(
                sequence.sequence_hash,
                gate,
                audit,
                transport,
                decision=decision,
                sizing=sizing,
                exit_reason=f"LISTED_CHAIN_{exc}",
            )
        selected = listed.instrument_id
    else:
        selected = select_option_contract(
            config.symbol,
            spot_close,
            decision.direction,
            config.option_expiry,
            config.option_moneyness,
        )
    instrument = SelectedInstrument(
        selection_id=replay_context.deterministic_id("SEL", selected),
        intent_id=opp_id,
        instrument_id=selected,
        selection_version="replay-v1",
        selected_at=trigger_snap.decision_time,
    )
    audit.append("instrument", instrument.selection_id, f"AUTH-{opp_id}")

    path = AdaptiveEdgeExecutionPath(transport=transport, formula_ids=required)
    side = "BUY"
    executed = path.submit_and_project(
        instrument=instrument,
        authorization=risk_auth,
        sizing=sizing,
        side=side,
        created_at=trigger_snap.decision_time,
        replay_context=replay_context,
        broker_event=BrokerExecutionEvent(
            broker_event_id="pending",
            order_intent_id="pending",
            broker_status="FILLED",
            event_time=trigger_snap.decision_time,
            filled_quantity=sizing.final_quantity,
            fill_price=entry_fill_price,
        ),
        risk_boundary=entry_fill_price - min(protection_policy.protective_stop_points or 10.0, 10.0)
        if protection_policy is not None
        else entry_fill_price - 10.0,
    )
    audit.append("order_intent", executed.order.order_intent_id, instrument.selection_id)
    audit.append("execution_event", executed.execution.execution_event_id, executed.order.order_intent_id)
    audit.append("position", executed.position.position_id, executed.execution.execution_event_id)

    policy = protection_policy or ProtectionPolicy("REPLAY_NOT_LIVE", protective_stop_points=10.0)
    managed = ManagedPosition.from_execution(executed, policy=policy)
    lifecycle_actions: list[str] = []
    protection_authorities: list[str] = []
    exit_reason: str | None = None
    exit_execution = None
    final_position = executed.position
    pnl_marks = [0.0]

    for later in bars[trigger_index + 1 :]:
        later_close = float(later.payload.get("close") or spot_close)
        option_mark = _simulated_option_mark(
            entry_fill_price,
            spot_close,
            later_close,
            decision.direction,
        )
        tick = managed.on_mark(option_mark, later.available_at)
        lifecycle_actions.append(tick.lifecycle.action)
        if tick.protection.authority:
            protection_authorities.append(tick.protection.authority)
        audit.append("lifecycle", tick.lifecycle.evaluation_id, executed.position.position_id)
        pnl_marks.append((option_mark - entry_fill_price) * executed.order.quantity)
        if tick.exit_required:
            closed = managed.flatten(path, fill_price=option_mark, event_time=later.available_at)
            exit_execution = closed.execution
            final_position = closed.position
            exit_reason = tick.lifecycle.action
            audit.append("lifecycle_exit", closed.execution.execution_event_id, executed.position.position_id)
            pnl_marks.append((option_mark - entry_fill_price) * executed.order.quantity)
            break

    if exit_execution is None:
        last_close = float(bars[-1].payload.get("close") or spot_close)
        option_mark = _simulated_option_mark(entry_fill_price, spot_close, last_close, decision.direction)
        end = managed.on_mark(option_mark, bars[-1].available_at, is_emergency=False)
        lifecycle_actions.append(end.lifecycle.action)
        if not managed.outcome_finalized:
            managed.finalize_outcome("END_OF_SEQUENCE")
            closed = managed.flatten(path, fill_price=option_mark, event_time=bars[-1].available_at)
            exit_execution = closed.execution
            final_position = closed.position
            exit_reason = "END_OF_SEQUENCE"
            audit.append("lifecycle_exit", closed.execution.execution_event_id, executed.position.position_id)
            pnl_marks.append((option_mark - entry_fill_price) * executed.order.quantity)

    realized = 0.0
    if exit_execution is not None and exit_execution.fill_price is not None:
        reconciled = reconcile_realized_pnl(
            side=executed.order.side,
            quantity=executed.order.quantity,
            entry_price=entry_fill_price,
            exit_price=exit_execution.fill_price,
            cost_params=cost_params,
        )
        realized = reconciled.net_pnl
    accounting = mark_accounting(tuple(pnl_marks))
    audit.append("pnl", f"PNL-{executed.order.order_intent_id}", executed.position.position_id)

    return FullStrategyReplayTrace(
        sequence_hash=sequence.sequence_hash,
        execution_gate=gate,
        decision=decision,
        horizon=decision.horizon.value,
        sizing=sizing,
        instrument_id=selected,
        order=executed.order,
        entry_execution=executed.execution,
        exit_execution=exit_execution,
        initial_position=executed.position,
        final_position=final_position,
        lifecycle_actions=tuple(lifecycle_actions),
        protection_authorities=tuple(protection_authorities),
        realized_pnl=round(realized, 4),
        accounting=accounting,
        submissions=len(transport.submitted_orders),
        audit=audit.records(),
        production_gate_authorized=gate.authorized,
        traded=True,
        exit_reason=exit_reason,
    )


def _simulated_option_mark(
    entry_fill: float,
    entry_spot: float,
    current_spot: float,
    direction: str,
) -> float:
    """Research mark map already used by strategy_pipeline. Not recovered F-112."""
    spot_delta = (current_spot - entry_spot) if direction == "BULLISH" else (entry_spot - current_spot)
    return max(1.0, entry_fill + spot_delta * 0.5)


def _blocked(
    sequence_hash: str,
    gate: ExecutionGateDecision,
    audit: AuditLedger,
    transport: SimulatedExecutionTransport,
    *,
    decision: MarketStateDecision | None = None,
    sizing: PositionSizingAssessment | None = None,
    traded: bool = False,
    exit_reason: str | None = None,
) -> FullStrategyReplayTrace:
    return FullStrategyReplayTrace(
        sequence_hash=sequence_hash,
        execution_gate=gate,
        decision=decision,
        horizon=None if decision is None else decision.horizon.value,
        sizing=sizing,
        instrument_id=None,
        order=None,
        entry_execution=None,
        exit_execution=None,
        initial_position=None,
        final_position=None,
        lifecycle_actions=(),
        protection_authorities=(),
        realized_pnl=0.0,
        accounting=None,
        submissions=len(transport.submitted_orders),
        audit=audit.records(),
        production_gate_authorized=gate.authorized,
        traded=traded,
        exit_reason=exit_reason,
    )
