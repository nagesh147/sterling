"""Research end-to-end path: F-101 score → simulated fill → lifecycle.

Does not call production require_execution_authorized().
Does not connect Kite. Does not unlock F-101..F-114.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Sequence

from .accounting import AccountingSnapshot, mark_accounting
from .broker_event_mapper import BrokerExecutionEvent
from .contracts import AdaptiveEdgeState, RiskAuthorization, RiskState
from .e2e import AuditLedger, SelectedInstrument
from .event_boundary import CanonicalMarketEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalExecutionStatus, CanonicalOrderIntent
from .execution_gate import evaluate_execution_gate
from .execution_path import AdaptiveEdgeExecutionPath
from .f101 import F101Parameters, F101Result
from .feature_engine import FeatureStatus
from .position_projector import DeterministicPositionProjector
from .research_formulas import assert_production_strategy_locked, research_formula_table
from .research_opportunity import ResearchOpportunity, evaluate_research_opportunity
from .research_pipeline import (
    CoverageReport,
    ResearchFoldSummary,
    ResearchQualityReport,
    ResearchWalkForwardEval,
    ResearchWalkForwardSpec,
    coverage_report,
    evaluate_research_walk_forward,
    partition_research_rows,
    quality_report,
    research_artifact_digest,
    summarize_research_folds,
)
from .research_references import executable_reference
from .lifecycle_engine import (
    A126LifecycleEngine,
    HorizonState,
    LifecycleEvidence,
    OverlayState,
    ProtectionState,
    ThesisState,
)
from .position_lifecycle import ManagedPosition
from .management import ManagementPolicy, ManagementSnapshot, evaluate_management
from .opportunity_mode import (
    ModeDecision,
    ModeEvidence,
    ModePolicy,
    ModeTransitionRecord,
    OpportunityMode,
    OpportunityModeEngine,
)
from .protection import ProtectionEngine, ProtectionPolicy
from .research_session import (
    a126_session_cutoff_reached,
    minutes_until_a126_cutoff,
    nse_regular_session,
    session_date_ist,
)
from .walk_forward import ObservationDisposition
from .state import StateEvent, transition
from .risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    PositionSizingAssessment,
    RiskPerUnitAssessment,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)
from .structure import StructureSnapshot, build_structure_series
from .trial_dataset import F101TrialObservation, score_trial_bars


class SimulatedBroker:
    def submit(self, intent: CanonicalOrderIntent) -> str:
        return f"SIM-{intent.order_intent_id}"


@dataclass(frozen=True)
class ResearchSizingInputs:
    """Caller-supplied research inputs. Not learned. Not F-111."""

    authorized_risk: float
    initial_stop: float
    cost_params: ExecutionCostParameters
    sizing_params: SizingParameters
    issued_at: str
    stop_points: float | None = None
    expected_gross_points: float | None = None


def _research_param(name: str, value: float, units: str = "INR") -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units=units,
        version="research-1",
        provenance="RESEARCH_NOT_LIVE_explicit",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def research_sizing_inputs(*, issued_at: str) -> ResearchSizingInputs:
    """1-lot research size at a 25-point stop. Not F-111. Not a live risk budget."""
    return ResearchSizingInputs(
        authorized_risk=80.0,
        initial_stop=1.0,
        stop_points=80.0,
        expected_gross_points=80.0,
        cost_params=ExecutionCostParameters(
            spread_cost=_research_param("spread_cost", 0.0),
            expected_slippage=_research_param("expected_slippage", 0.0),
            brokerage_per_unit=_research_param("brokerage_per_unit", 0.0),
            exchange_charges_per_unit=_research_param("exchange_charges_per_unit", 0.0),
            taxes_per_unit=_research_param("taxes_per_unit", 0.0),
            latency_cost_per_unit=_research_param("latency_cost_per_unit", 0.0),
        ),
        sizing_params=SizingParameters(
            max_position_qty=_research_param("max_position_qty", 1.0, "contracts"),
            max_capital_allocation=_research_param("max_capital_allocation", 10_000_000.0),
            lot_size=_research_param("lot_size", 1.0, "contracts"),
        ),
        issued_at=issued_at,
    )


@dataclass(frozen=True)
class ResearchE2EResult:
    label: str
    coverage: CoverageReport
    scored: int
    traded: bool
    skip_reason: str | None
    f101: F101Result | None
    opportunity: ResearchOpportunity | None
    side: str | None
    reference_formula_id: str | None
    order: CanonicalOrderIntent | None
    fill_price: float | None
    position_quantity: int
    risk_per_unit: RiskPerUnitAssessment | None
    sizing: PositionSizingAssessment | None
    accounting: AccountingSnapshot | None
    lifecycle_action: str | None
    engine_state: AdaptiveEdgeState | None
    production_gate_authorized: bool
    formula_gaps: tuple[str, ...]


@dataclass(frozen=True)
class ResearchSessionLeg:
    session_date: str
    entry_time: str
    exit_time: str | None
    flattened: bool
    quantity: int
    symbol: str = "NIFTY-I"
    side: str = "BUY"
    entry_price: float | None = None
    exit_price: float | None = None
    stop_price: float | None = None
    trail_price: float | None = None
    lock_price: float | None = None
    entry_score: float | None = None
    entry_mode: str = "MICRO"
    exit_mode: str | None = None
    peak_mode: str = "MICRO"
    thesis: str = "THESIS_VALID"
    protection_stage: str = "P0_RISK_CONTROLLED"
    overlays: tuple[str, ...] = ()
    operating_mode: str = "active"
    horizon: str = "IMPULSE"
    entry_poc: float | None = None
    entry_vwap: float | None = None
    entry_cvd: float | None = None


@dataclass(frozen=True)
class ResearchDayLedger:
    session_date: str
    entries: int
    exits: int
    last_quantity: int
    flattened: bool


@dataclass(frozen=True)
class ResearchHoldoutReplay:
    """TEST-window replay using TRAIN-only params. Not an A197 promotion."""

    label: str
    entries: int
    exits: int
    reentries: int
    last_position_quantity: int
    parameter_status: str
    used_train_params_only: bool
    test_bar_count: int
    software_complete: bool
    incomplete_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ResearchSessionResult:
    """Bar-by-bar research replay. One active position (INV-ENTRY-003). Not F-111."""

    label: str
    coverage: CoverageReport
    scored: int
    entries: int
    blocked_pyramid: int
    exits: int
    reentries: int
    marks: int
    last_accounting: AccountingSnapshot | None
    last_order: CanonicalOrderIntent | None
    last_lifecycle_action: str | None
    last_position_quantity: int
    exit_fill_price: float | None
    audit_stages: tuple[str, ...]
    walk_forward: ResearchFoldSummary | None
    walk_forward_eval: ResearchWalkForwardEval | None
    legs: tuple[ResearchSessionLeg, ...]
    daily: tuple[ResearchDayLedger, ...]
    quality: ResearchQualityReport | None
    holdout: ResearchHoldoutReplay | None
    last_mode: str | None
    mode_counts: tuple[tuple[str, int], ...]
    mode_transitions: tuple[ModeTransitionRecord, ...]
    last_thesis: str | None
    last_protection_stage: str | None
    last_overlays: tuple[str, ...]
    last_operating_mode: str | None
    last_horizon: str | None
    last_poc: float | None
    last_cvd: float | None
    last_location: str | None
    last_bar_delta: float | None
    last_vwap: float | None
    last_or_location: str | None
    last_poc_migration: str | None
    artifact_digest: str
    production_gate_authorized: bool
    formula_gaps: tuple[str, ...]
    software_complete: bool
    incomplete_reasons: tuple[str, ...]


REQUIRED_ENTRY_STAGES = ("opportunity", "order_intent", "execution_event", "accounting")


def research_session_completeness(
    result: "ResearchSessionResult",
) -> tuple[bool, tuple[str, ...]]:
    """Software-complete if the recovered research path ran with production still locked."""
    missing: list[str] = []
    if result.label != "RESEARCH_NOT_LIVE":
        missing.append("label_must_be_RESEARCH_NOT_LIVE")
    if result.coverage.status.startswith("A197") and not result.coverage.meets_a197:
        missing.append("coverage_must_not_claim_a197")
    if result.entries < 1:
        missing.append("no_entry")
    else:
        stages = set(result.audit_stages)
        for stage in REQUIRED_ENTRY_STAGES:
            if stage not in stages:
                missing.append(f"missing_audit:{stage}")
        if result.last_accounting is None:
            missing.append("missing_accounting")
        if result.last_order is None:
            missing.append("missing_order")
    if result.entries > result.exits + 1:
        missing.append("entries_exceed_exits_plus_open_leg")
    if result.entries >= 1 and len(result.legs) != result.entries:
        missing.append("leg_count_mismatch")
    if (
        result.holdout is not None
        and result.holdout.entries >= 1
        and not result.holdout.used_train_params_only
    ):
        missing.append("holdout_must_use_train_params")
    if result.exits >= 1:
        if result.exit_fill_price is None:
            missing.append("missing_exit_fill")
        stages = set(result.audit_stages)
        if not {"session_cutoff_exit", "protection_exit", "thesis_exit", "economic_exit"} & stages:
            missing.append("missing_audit:exit")
        if result.entries == result.exits and result.last_position_quantity != 0:
            missing.append("cutoff_exit_must_flatten_to_zero")
    if result.walk_forward is not None and result.walk_forward.train_test_overlap:
        missing.append("walk_forward_train_test_overlap")
    if (
        result.walk_forward_eval is not None
        and result.walk_forward_eval.summary.train_test_overlap
    ):
        missing.append("walk_forward_eval_train_test_overlap")
    if result.formula_gaps and "F-101" in result.formula_gaps:
        missing.append("f101_must_not_be_spec_gap")
    if result.quality is None:
        missing.append("missing_quality")
    elif result.quality.meets_a197:
        missing.append("quality_must_not_claim_a197")
    elif result.quality.status != "TRIAL_NOT_A197_QUALITY":
        missing.append("quality_status")
    if result.entries >= 1 and not result.daily:
        missing.append("missing_daily_ledger")
    if (
        result.walk_forward_eval is not None
        and result.walk_forward_eval.estimated_from_train_only
        and result.holdout is None
    ):
        missing.append("missing_holdout")
    if not result.artifact_digest:
        missing.append("missing_artifact_digest")
    return (not missing, tuple(missing))


def _is_scored(item: F101TrialObservation) -> bool:
    return item.result.status is FeatureStatus.VALID and item.result.score is not None


def _select_valid(
    rows: Sequence[F101TrialObservation],
    *,
    which: str,
    skip_cutoff: bool = False,
    allowed_ids: set[str] | None = None,
) -> F101TrialObservation | None:
    sequence: Sequence[F101TrialObservation] = rows if which == "first" else list(reversed(rows))
    for item in sequence:
        if not _is_scored(item):
            continue
        if allowed_ids is not None and item.bar_record_id not in allowed_ids:
            continue
        if skip_cutoff and a126_session_cutoff_reached(item.decision_time):
            continue
        return item
    return None


def _holding_age_seconds(start: str, now: str) -> float:
    begin = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(now.replace("Z", "+00:00"))
    return max(0.0, (end - begin).total_seconds())


def _mode_rank(mode: OpportunityMode) -> int:
    return (
        OpportunityMode.MICRO,
        OpportunityMode.SCALP,
        OpportunityMode.EXTENDED_SCALP,
        OpportunityMode.INTRADAY,
    ).index(mode)


def _daily_from_legs(legs: Sequence[ResearchSessionLeg]) -> tuple[ResearchDayLedger, ...]:
    grouped: dict[str, list[ResearchSessionLeg]] = {}
    for leg in legs:
        grouped.setdefault(leg.session_date, []).append(leg)
    return tuple(
        ResearchDayLedger(
            session_date=day,
            entries=len(items),
            exits=sum(1 for item in items if item.flattened),
            last_quantity=items[-1].quantity,
            flattened=items[-1].flattened,
        )
        for day, items in grouped.items()
    )


def run_research_e2e(
    *,
    symbol: str,
    bar_events: Sequence[CanonicalMarketEvent],
    tick_events: Sequence[CanonicalMarketEvent],
    params: F101Parameters,
    bar_sequence_hash: str,
    tick_sequence_hash: str,
    quantity: int = 1,
    sizing_inputs: ResearchSizingInputs | None = None,
    select: str = "last",
    min_bar_index: int = 0,
    allowed_bar_ids: set[str] | None = None,
) -> ResearchE2EResult:
    assert_production_strategy_locked()
    gate = evaluate_execution_gate()
    rows = score_trial_bars(
        bar_events=bar_events, tick_events=tick_events, params=params
    )
    coverage = coverage_report(
        symbol=symbol,
        observations=rows,
        tick_count=len(tick_events),
        bar_sequence_hash=bar_sequence_hash,
        tick_sequence_hash=tick_sequence_hash,
    )
    coverage.assert_not_a197()
    gaps = tuple(
        item.formula_id
        for item in research_formula_table().values()
        if item.status == "SPEC_GAP"
    )

    def _empty(reason: str, chosen_result: F101Result | None = None) -> ResearchE2EResult:
        return ResearchE2EResult(
            label="RESEARCH_NOT_LIVE",
            coverage=coverage,
            scored=len(rows),
            traded=False,
            skip_reason=reason,
            f101=chosen_result,
            opportunity=None,
            side=None,
            reference_formula_id=None,
            order=None,
            fill_price=None,
            position_quantity=0,
            risk_per_unit=None,
            sizing=None,
            accounting=None,
            lifecycle_action=None,
            engine_state=None,
            production_gate_authorized=gate.authorized,
            formula_gaps=gaps,
        )

    eligible = [row for row in rows if row.bar_index >= min_bar_index]
    scored = [
        row
        for row in eligible
        if _is_scored(row)
        and (allowed_bar_ids is None or row.bar_record_id in allowed_bar_ids)
    ]
    if scored and all(a126_session_cutoff_reached(row.decision_time) for row in scored):
        return _empty("a126_session_cutoff", scored[0].result)
    chosen = _select_valid(
        eligible, which=select, skip_cutoff=True, allowed_ids=allowed_bar_ids
    )
    if chosen is None:
        return _empty("no_valid_f101_score")

    side = "BUY" if (chosen.result.score or 0.0) >= 0 else "SELL"
    reference = executable_reference(tick_events, chosen.decision_time, side)
    if reference.status is not FeatureStatus.VALID or reference.price is None:
        return _empty("missing_executable_reference", chosen.result)

    risk_unit: RiskPerUnitAssessment | None = None
    sizing: PositionSizingAssessment | None = None
    trade_qty = quantity
    risk_authorized: bool | None = None
    capital_quantity: int | None = None
    auth: RiskAuthorization | None = None
    expected_gross: float | None = None
    execution_cost: float | None = None
    if sizing_inputs is not None and sizing_inputs.expected_gross_points is not None:
        expected_gross = sizing_inputs.expected_gross_points
        execution_cost = 0.0
    if sizing_inputs is not None:
        stop_px = sizing_inputs.initial_stop
        if sizing_inputs.stop_points is not None:
            stop_px = reference.price - abs(sizing_inputs.stop_points)
        risk_unit = calculate_risk_per_unit(
            reference.price,
            stop_px,
            sizing_inputs.cost_params,
        )
        auth = RiskAuthorization(
            opportunity_id=f"RESEARCH-{chosen.bar_record_id}",
            authorized_risk=sizing_inputs.authorized_risk,
            risk_state=RiskState.AUTHORIZED,
            policy_version="research-not-live",
            issued_at=sizing_inputs.issued_at,
        )
        sizing = calculate_position_sizing(auth, risk_unit, sizing_inputs.sizing_params)
        if not sizing.valid or sizing.final_quantity <= 0:
            return _empty(sizing.reason or "sizing_not_executable", chosen.result)
        trade_qty = sizing.final_quantity
        risk_authorized = True
        capital_quantity = trade_qty

    opportunity = evaluate_research_opportunity(
        opportunity_id=f"RESEARCH-{chosen.bar_record_id}",
        snapshot=chosen.snapshot,
        f101=chosen.result,
        side=side,
        reference=reference,
        risk_authorized=risk_authorized,
        capital_quantity=capital_quantity,
        session_valid=nse_regular_session(chosen.decision_time),
        expected_gross_value=expected_gross,
        execution_cost=execution_cost,
    )
    engine = transition(AdaptiveEdgeState(), StateEvent.OPPORTUNITY_DETECTED).resulting_state
    if not opportunity.recovered_conjunction:
        engine = transition(engine, StateEvent.OPPORTUNITY_REJECTED).resulting_state
        return _empty("recovered_entry_gates_failed", chosen.result)
    engine = transition(engine, StateEvent.OPPORTUNITY_VALIDATED).resulting_state
    if auth is not None:
        engine = AdaptiveEdgeState(
            mode=engine.mode,
            risk_state=auth.risk_state,
            opportunity_state=engine.opportunity_state,
            authorization=auth,
        )
    engine = transition(engine, StateEvent.ACTIVATE).resulting_state

    path = AdaptiveEdgeExecutionPath(transport=SimulatedBroker(), formula_ids=())
    fill_event = BrokerExecutionEvent(
        broker_event_id=f"SIMFILL-{chosen.bar_record_id}",
        order_intent_id="pending",
        broker_status="FILLED",
        event_time=chosen.decision_time,
        filled_quantity=trade_qty,
        fill_price=reference.price,
    )
    if auth is not None and sizing is not None:
        instrument = SelectedInstrument(
            selection_id=f"SEL-{chosen.bar_record_id}",
            intent_id=auth.opportunity_id,
            instrument_id=symbol,
            selection_version="research-1",
            selected_at=chosen.decision_time,
        )
        executed = path.submit_and_project(
            instrument=instrument,
            authorization=auth,
            sizing=sizing,
            side=side,
            created_at=chosen.decision_time,
            broker_event=fill_event,
        )
        order = executed.order
        position = executed.position
    else:
        order = CanonicalOrderIntent(
            order_intent_id=f"RESEARCH-{chosen.bar_record_id}",
            selection_id=f"SEL-{symbol}",
            instrument_id=symbol,
            side=side,
            quantity=trade_qty,
            intent_version="research-1",
            idempotency_key=f"research-{chosen.bar_record_id}",
            created_at=chosen.decision_time,
        )
        path.submit(order)
        fill_event = BrokerExecutionEvent(
            broker_event_id=f"SIMFILL-{chosen.bar_record_id}",
            order_intent_id=order.order_intent_id,
            broker_status="FILLED",
            event_time=chosen.decision_time,
            filled_quantity=trade_qty,
            fill_price=reference.price,
        )
        position = path.receive_and_project(
            fill_event,
            instrument_id=symbol,
            side=order.side,
            position_id=f"POS-{symbol}",
        ).position
    mark = float(bar_events[chosen.bar_index].payload["close"])
    signed = 1.0 if order.side == "BUY" else -1.0
    current_pnl = (mark - reference.price) * signed * trade_qty
    accounting = mark_accounting((0.0, current_pnl))
    policy = ProtectionPolicy(label="RESEARCH_NOT_LIVE")
    if sizing_inputs is not None and sizing_inputs.stop_points is not None:
        policy = ProtectionPolicy(
            label="RESEARCH_NOT_LIVE",
            protective_stop_points=abs(sizing_inputs.stop_points),
        )
    managed = ManagedPosition(
        position,
        side=order.side,
        entry_price=reference.price,
        policy=policy,
        authorization_id=order.authorization_id or auth.opportunity_id if auth is not None else order.order_intent_id,
        entry_order=order,
    )
    lifecycle = managed.on_mark(mark, bar_events[chosen.bar_index].available_at).lifecycle
    return ResearchE2EResult(
        label="RESEARCH_NOT_LIVE",
        coverage=coverage,
        scored=len(rows),
        traded=True,
        skip_reason=None,
        f101=chosen.result,
        opportunity=opportunity,
        side=side,
        reference_formula_id=reference.formula_id,
        order=order,
        fill_price=reference.price,
        position_quantity=position.quantity,
        risk_per_unit=risk_unit,
        sizing=sizing,
        accounting=accounting,
        lifecycle_action=lifecycle.action,
        engine_state=engine,
        production_gate_authorized=gate.authorized,
        formula_gaps=gaps,
    )


def run_research_session(
    *,
    symbol: str,
    bar_events: Sequence[CanonicalMarketEvent],
    tick_events: Sequence[CanonicalMarketEvent],
    params: F101Parameters,
    bar_sequence_hash: str,
    tick_sequence_hash: str,
    quantity: int = 1,
    sizing_inputs: ResearchSizingInputs | None = None,
    walk_forward_spec: ResearchWalkForwardSpec | None = None,
    allowed_bar_ids: set[str] | None = None,
    run_holdout: bool = True,
    protection_policy: ProtectionPolicy | None = None,
    mode_policy: ModePolicy | None = None,
    management_policy: ManagementPolicy | None = None,
) -> ResearchSessionResult:
    """Walk bars: enter when flat and before A126 cutoff; flatten at cutoff; no pyramid."""
    probe = run_research_e2e(
        symbol=symbol,
        bar_events=bar_events,
        tick_events=tick_events,
        params=params,
        bar_sequence_hash=bar_sequence_hash,
        tick_sequence_hash=tick_sequence_hash,
        quantity=quantity,
        sizing_inputs=sizing_inputs,
        select="first",
        min_bar_index=0,
        allowed_bar_ids=allowed_bar_ids,
    )
    rows = score_trial_bars(
        bar_events=bar_events, tick_events=tick_events, params=params
    )
    structure_series = build_structure_series(bar_events, tick_events)
    entries = 0
    reentries = 0
    exits = 0
    blocked = 0
    marks = 0
    pnl_history = [0.0]
    last_order = None
    last_action = None
    last_qty = 0
    exit_px: float | None = None
    audit = AuditLedger()
    raw_legs: list[ResearchSessionLeg] = []
    all_mode_records: list[ModeTransitionRecord] = []
    last_mode_seen: str | None = None
    last_thesis: str | None = None
    last_stage: str | None = None
    last_overlays: tuple[str, ...] = ()
    last_posture: str | None = None
    last_horizon: str | None = None
    last_poc: float | None = None
    last_cvd: float | None = None
    last_location: str | None = None
    last_bar_delta: float | None = None
    last_vwap: float | None = None
    last_or_location: str | None = None
    last_poc_migration: str | None = None
    cursor = 0
    while cursor < len(rows):
        opened = run_research_e2e(
            symbol=symbol,
            bar_events=bar_events,
            tick_events=tick_events,
            params=params,
            bar_sequence_hash=bar_sequence_hash,
            tick_sequence_hash=tick_sequence_hash,
            quantity=quantity,
            sizing_inputs=sizing_inputs,
            select="first",
            min_bar_index=cursor,
            allowed_bar_ids=allowed_bar_ids,
        )
        if not opened.traded or opened.order is None or opened.fill_price is None:
            break
        if entries:
            reentries += 1
        entries += 1
        last_order = opened.order
        last_action = opened.lifecycle_action
        last_qty = opened.order.quantity
        audit.append("opportunity", f"RESEARCH-{opened.order.order_intent_id}", opened.order.created_at)
        audit.append("order_intent", opened.order.order_intent_id, f"RESEARCH-{opened.order.order_intent_id}")
        audit.append("execution_event", f"SIMFILL-{opened.order.order_intent_id}", opened.order.order_intent_id)
        audit.append("accounting", f"MARK-{opened.order.order_intent_id}", opened.order.order_intent_id)
        entry_id = opened.order.order_intent_id.removeprefix("RESEARCH-")
        entry_row = next(row for row in rows if row.bar_record_id == entry_id)
        entry_structure = (
            structure_series[entry_row.bar_index]
            if 0 <= entry_row.bar_index < len(structure_series)
            else None
        )
        raw_legs.append(
            ResearchSessionLeg(
                session_date=session_date_ist(opened.order.created_at),
                entry_time=opened.order.created_at,
                exit_time=None,
                flattened=False,
                quantity=opened.order.quantity,
                symbol=symbol,
                side=opened.order.side,
                entry_price=opened.fill_price,
                entry_score=entry_row.result.score,
                entry_poc=None if entry_structure is None else entry_structure.poc,
                entry_vwap=None if entry_structure is None else entry_structure.vwap,
                entry_cvd=None if entry_structure is None else entry_structure.cvd,
            )
        )
        signed = 1.0 if opened.order.side == "BUY" else -1.0
        if opened.accounting is not None:
            pnl_history.append(opened.accounting.current_pnl)
            marks += 1
        side_map = {opened.order.order_intent_id: opened.order.side}
        projector = DeterministicPositionProjector(
            f"POS-{symbol}-{entries}",
            symbol,
            side=opened.order.side,
            order_side_map=side_map,
        )
        position = projector.project(
            CanonicalExecutionEvent(
                execution_event_id=f"SIMFILL-{opened.order.order_intent_id}",
                order_intent_id=opened.order.order_intent_id,
                event_type=CanonicalExecutionStatus.FILLED,
                event_time=opened.order.created_at,
                filled_quantity=opened.order.quantity,
                fill_price=opened.fill_price,
            )
        )
        last_qty = position.quantity
        lifecycle = A126LifecycleEngine(position.position_id)
        protector = (
            ProtectionEngine(
                protection_policy,
                side=opened.order.side,
                entry_price=opened.fill_price,
            )
            if protection_policy is not None
            else None
        )
        last_stop = None
        last_trail = None
        last_lock = None
        if protector is not None and opened.fill_price is not None:
            opened_protection = protector.update(opened.fill_price)
            last_stop = opened_protection.stop_price
            last_trail = opened_protection.trail_price
            last_lock = opened_protection.lock_price
            raw_legs[-1] = replace(
                raw_legs[-1],
                stop_price=last_stop,
                trail_price=last_trail,
                lock_price=last_lock,
            )
        mode_engine = (
            OpportunityModeEngine(mode_policy, started_at=opened.order.created_at)
            if mode_policy is not None
            else None
        )
        peak_mode = OpportunityMode.MICRO
        last_mode_name = OpportunityMode.MICRO.value
        extreme_fav = 0.0
        misaligned_streak = 0
        last_mgmt: ManagementSnapshot | None = None
        flattened = False
        next_cursor = len(rows)
        for row in rows:
            if row.bar_index <= entry_row.bar_index:
                continue
            cutoff = a126_session_cutoff_reached(row.decision_time)
            mark = float(bar_events[row.bar_index].payload["close"])
            decision = protector.update(mark) if protector is not None else None
            if decision is not None:
                last_stop = decision.stop_price
                last_trail = decision.trail_price
                last_lock = decision.lock_price
            mode_decision: ModeDecision | None = None
            if mode_engine is not None:
                current_fav = (mark - opened.fill_price) * signed
                extreme_fav = max(extreme_fav, current_fav)
                giveback_ratio = (
                    0.0
                    if extreme_fav <= 0
                    else max(0.0, (extreme_fav - current_fav) / extreme_fav)
                )
                entry_dt = opened.order.created_at
                age = _holding_age_seconds(entry_dt, row.decision_time)
                aligned = (
                    row.result.status is FeatureStatus.VALID
                    and row.result.score is not None
                    and ((row.result.score >= 0) == (opened.order.side == "BUY"))
                )
                mode_decision = mode_engine.update(
                    ModeEvidence(
                        score_aligned=aligned,
                        features_valid=row.result.status is FeatureStatus.VALID,
                        data_certain=row.result.status is FeatureStatus.VALID,
                        favorable_points=max(0.0, current_fav),
                        giveback_ratio=giveback_ratio,
                        minutes_to_cutoff=minutes_until_a126_cutoff(row.decision_time),
                        holding_age_seconds=age,
                    ),
                    timestamp=row.decision_time,
                )
                last_mode_name = mode_decision.mode.value
                if _mode_rank(mode_decision.mode) > _mode_rank(peak_mode):
                    peak_mode = mode_decision.mode
            current_fav = (mark - opened.fill_price) * signed
            extreme_fav = max(extreme_fav, current_fav)
            giveback_ratio = (
                0.0 if extreme_fav <= 0 else max(0.0, (extreme_fav - current_fav) / extreme_fav)
            )
            aligned = (
                row.result.status is FeatureStatus.VALID
                and row.result.score is not None
                and ((row.result.score >= 0) == (opened.order.side == "BUY"))
            )
            if aligned:
                misaligned_streak = 0
            else:
                misaligned_streak += 1
            minutes_left = minutes_until_a126_cutoff(row.decision_time)
            structure = (
                structure_series[row.bar_index]
                if 0 <= row.bar_index < len(structure_series)
                else None
            )
            if structure is not None:
                last_poc = structure.poc
                last_cvd = structure.cvd
                last_location = structure.location
                last_bar_delta = structure.bar_delta
                last_vwap = structure.vwap
                last_or_location = structure.or_location
                last_poc_migration = structure.poc_migration
            if management_policy is not None:
                last_mgmt = evaluate_management(
                    score_aligned=aligned,
                    features_valid=row.result.status is FeatureStatus.VALID,
                    li_valid=row.snapshot.statuses.get("LiquidityImbalance") is FeatureStatus.VALID,
                    giveback_ratio=giveback_ratio,
                    favorable_points=max(0.0, current_fav),
                    peak_favorable_points=max(0.0, extreme_fav),
                    misaligned_streak=misaligned_streak,
                    minutes_to_cutoff=minutes_left,
                    volatility_ratio=row.snapshot.values.get("VolatilityRatio"),
                    opportunity_mode=None if mode_decision is None else mode_decision.mode,
                    protection=decision,
                    stop_points=None if protection_policy is None else protection_policy.protective_stop_points,
                    cutoff=cutoff,
                    in_position=True,
                    policy=management_policy,
                    structure=structure,
                    side=opened.order.side,
                )
            want_h4 = bool(last_mgmt and last_mgmt.want_session_extension)
            evidence = LifecycleEvidence(
                session_cutoff_reached=cutoff,
                protective_stop_hit=bool(decision and decision.reason == "protective_stop_hit"),
                trailing_hit=bool(decision and decision.reason == "trailing_hit"),
                profit_lock_hit=bool(decision and decision.reason == "profit_lock_hit"),
                persistence_evidence_valid=bool(
                    (mode_decision and mode_decision.promoted)
                    or (
                        want_h4
                        and lifecycle.current_horizon is HorizonState.SESSION_TREND
                    )
                ),
                persistence_decayed=bool(mode_decision and mode_decision.downgraded),
                thesis_valid=last_mgmt.thesis is not ThesisState.THESIS_INVALID if last_mgmt else True,
                thesis_state=last_mgmt.thesis if last_mgmt else ThesisState.THESIS_VALID,
                economic_edge_valid=OverlayState.ECONOMIC_COLLAPSE not in (last_mgmt.overlays if last_mgmt else ()),
                liquidity_healthy=OverlayState.LIQUIDITY_STRESS not in (last_mgmt.overlays if last_mgmt else ()),
                data_certain=OverlayState.DATA_UNCERTAINTY not in (last_mgmt.overlays if last_mgmt else ()),
                suggested_protection=last_mgmt.protection_stage if last_mgmt else None,
            )
            last_action = lifecycle.evaluate_with_evidence(
                position, evidence, row.decision_time
            ).action
            pnl_history.append((mark - opened.fill_price) * signed * opened.order.quantity)
            marks += 1
            if last_action in {
                "EXIT_SESSION_CUTOFF",
                "EXIT_HARD_STOP",
                "EXIT_PROFIT_PROTECTION",
                "EXIT_THESIS_INVALID",
                "EXIT_ECONOMIC_COLLAPSE",
                "EXIT_EMERGENCY",
            }:
                close_side = "SELL" if opened.order.side == "BUY" else "BUY"
                close_ref = executable_reference(tick_events, row.decision_time, close_side)
                if close_ref.status is FeatureStatus.VALID and close_ref.price is not None:
                    close_order = CanonicalOrderIntent(
                        order_intent_id=f"RESEARCH-EXIT-{row.bar_record_id}",
                        selection_id=f"SEL-{symbol}",
                        instrument_id=symbol,
                        side=close_side,
                        quantity=opened.order.quantity,
                        intent_version="research-1",
                        idempotency_key=f"research-exit-{row.bar_record_id}",
                        created_at=row.decision_time,
                    )
                    exit_path = AdaptiveEdgeExecutionPath(transport=SimulatedBroker(), formula_ids=())
                    side_map[close_order.order_intent_id] = close_side
                    broker_ref = exit_path.submit(close_order)
                    exit_event = exit_path.receive(
                        BrokerExecutionEvent(
                            broker_event_id=f"SIMEXIT-{row.bar_record_id}",
                            order_intent_id=close_order.order_intent_id,
                            broker_status="FILLED",
                            event_time=row.decision_time,
                            broker_reference=broker_ref,
                            filled_quantity=opened.order.quantity,
                            fill_price=close_ref.price,
                        )
                    )
                    position = projector.project(exit_event)
                    last_order = close_order
                    exit_px = close_ref.price
                    last_qty = position.quantity
                    pnl_history.append(
                        (close_ref.price - opened.fill_price) * signed * opened.order.quantity
                    )
                    audit.append("order_intent", close_order.order_intent_id, opened.order.order_intent_id)
                    audit.append("execution_event", f"SIMEXIT-{row.bar_record_id}", close_order.order_intent_id)
                    if last_action == "EXIT_SESSION_CUTOFF":
                        stage = "session_cutoff_exit"
                    elif last_action == "EXIT_THESIS_INVALID":
                        stage = "thesis_exit"
                    elif last_action == "EXIT_ECONOMIC_COLLAPSE":
                        stage = "economic_exit"
                    else:
                        stage = "protection_exit"
                    audit.append(stage, f"EXIT-{row.bar_record_id}", close_order.order_intent_id)
                    raw_legs[-1] = replace(
                        raw_legs[-1],
                        exit_time=row.decision_time,
                        flattened=True,
                        quantity=last_qty,
                        exit_price=close_ref.price,
                        stop_price=last_stop,
                        trail_price=last_trail,
                        lock_price=last_lock,
                        exit_mode=last_mode_name,
                        peak_mode=peak_mode.value,
                        thesis=last_mgmt.thesis.value if last_mgmt else raw_legs[-1].thesis,
                        protection_stage=(
                            last_mgmt.protection_stage.value
                            if last_mgmt
                            else raw_legs[-1].protection_stage
                        ),
                        overlays=tuple(item.value for item in last_mgmt.overlays) if last_mgmt else (),
                        operating_mode=(
                            last_mgmt.operating_mode.value
                            if last_mgmt
                            else raw_legs[-1].operating_mode
                        ),
                        horizon=lifecycle.current_horizon.value,
                    )
                exits += 1
                flattened = True
                next_cursor = row.bar_index + 1
                break
            if row.result.status is FeatureStatus.VALID:
                blocked += 1
        last_horizon = lifecycle.current_horizon.value
        if last_mgmt is not None:
            last_thesis = last_mgmt.thesis.value
            last_stage = last_mgmt.protection_stage.value
            last_overlays = tuple(item.value for item in last_mgmt.overlays)
            last_posture = last_mgmt.operating_mode.value
        if mode_engine is not None:
            all_mode_records.extend(mode_engine.records)
            last_mode_seen = last_mode_name
            if not flattened:
                raw_legs[-1] = replace(
                    raw_legs[-1],
                    exit_mode=last_mode_name,
                    peak_mode=peak_mode.value,
                    stop_price=last_stop,
                    trail_price=last_trail,
                    lock_price=last_lock,
                    thesis=last_mgmt.thesis.value if last_mgmt else raw_legs[-1].thesis,
                    protection_stage=(
                        last_mgmt.protection_stage.value
                        if last_mgmt
                        else raw_legs[-1].protection_stage
                    ),
                    overlays=tuple(item.value for item in last_mgmt.overlays) if last_mgmt else (),
                    operating_mode=(
                        last_mgmt.operating_mode.value
                        if last_mgmt
                        else raw_legs[-1].operating_mode
                    ),
                    horizon=lifecycle.current_horizon.value,
                )
        if not flattened:
            break
        cursor = next_cursor

    folds = (
        summarize_research_folds(rows, walk_forward_spec) if walk_forward_spec is not None else None
    )
    wf_eval = (
        evaluate_research_walk_forward(
            rows,
            walk_forward_spec,
            w_short=params.w_short,
            w_long=params.w_long,
        )
        if walk_forward_spec is not None
        else None
    )
    quality = quality_report(
        probe.coverage,
        rows,
        session_valid=nse_regular_session,
        cutoff_reached=a126_session_cutoff_reached,
    )
    holdout: ResearchHoldoutReplay | None = None
    if (
        run_holdout
        and walk_forward_spec is not None
        and wf_eval is not None
        and wf_eval.estimated_from_train_only
        and wf_eval.train_med is not None
        and wf_eval.train_scale is not None
    ):
        test_ids = {
            row.bar_record_id
            for row in partition_research_rows(rows, walk_forward_spec)[ObservationDisposition.TEST]
        }
        if test_ids:
            holdout_params = F101Parameters(
                status="TRIAL_NOT_A197_TRAIN_ONLY",
                w_short=params.w_short,
                w_long=params.w_long,
                med=wf_eval.train_med,
                scale=wf_eval.train_scale,
                weights=params.weights,
            )
            child = run_research_session(
                symbol=symbol,
                bar_events=bar_events,
                tick_events=tick_events,
                params=holdout_params,
                bar_sequence_hash=bar_sequence_hash,
                tick_sequence_hash=tick_sequence_hash,
                quantity=quantity,
                sizing_inputs=sizing_inputs,
                walk_forward_spec=None,
                allowed_bar_ids=test_ids,
                run_holdout=False,
                protection_policy=protection_policy,
                mode_policy=mode_policy,
                management_policy=management_policy,
            )
            holdout = ResearchHoldoutReplay(
                label="RESEARCH_HOLDOUT_NOT_LIVE",
                entries=child.entries,
                exits=child.exits,
                reentries=child.reentries,
                last_position_quantity=child.last_position_quantity,
                parameter_status=holdout_params.status,
                used_train_params_only=True,
                test_bar_count=len(test_ids),
                software_complete=child.software_complete,
                incomplete_reasons=child.incomplete_reasons,
            )
    legs = tuple(raw_legs)
    finished = ResearchSessionResult(
        label="RESEARCH_NOT_LIVE",
        coverage=probe.coverage,
        scored=probe.scored,
        entries=entries,
        blocked_pyramid=blocked,
        exits=exits,
        reentries=reentries,
        marks=marks,
        last_accounting=mark_accounting(pnl_history) if marks else probe.accounting,
        last_order=last_order,
        last_lifecycle_action=last_action,
        last_position_quantity=last_qty,
        exit_fill_price=exit_px,
        audit_stages=tuple(record.stage for record in audit.records()),
        walk_forward=folds,
        walk_forward_eval=wf_eval,
        legs=legs,
        daily=_daily_from_legs(legs),
        quality=quality,
        holdout=holdout,
        last_mode=last_mode_seen,
        mode_counts=tuple(
            (name, sum(1 for rec in all_mode_records if rec.new_mode.value == name))
            for name in ("MICRO", "SCALP", "EXTENDED_SCALP", "INTRADAY")
        ),
        mode_transitions=tuple(all_mode_records),
        last_thesis=last_thesis,
        last_protection_stage=last_stage,
        last_overlays=last_overlays,
        last_operating_mode=last_posture,
        last_horizon=last_horizon,
        last_poc=last_poc,
        last_cvd=last_cvd,
        last_location=last_location,
        last_bar_delta=last_bar_delta,
        last_vwap=last_vwap,
        last_or_location=last_or_location,
        last_poc_migration=last_poc_migration,
        artifact_digest=research_artifact_digest(
            bar_sequence_hash=probe.coverage.bar_sequence_hash,
            tick_sequence_hash=probe.coverage.tick_sequence_hash,
            label="RESEARCH_NOT_LIVE",
        ),
        production_gate_authorized=probe.production_gate_authorized,
        formula_gaps=probe.formula_gaps,
        software_complete=False,
        incomplete_reasons=(),
    )
    complete, reasons = research_session_completeness(finished)
    return ResearchSessionResult(
        **{**finished.__dict__, "software_complete": complete, "incomplete_reasons": reasons}
    )
