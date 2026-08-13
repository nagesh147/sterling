"""End-to-end Adaptive Edge orchestration contracts.

This module composes existing canonical boundaries. It does not invent locked
strategy mathematics. Any unresolved strategy formula or downstream contract
fails closed through the supplied implementation boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Mapping, Protocol, TypeVar

from .edge import EdgeAssessment, EdgeFormula, evaluate_edge
from .economic import EconomicAssessment, evaluate_economics
from .event_boundary import CanonicalMarketEvent
from .execution_gate import ExecutionGateDecision, evaluate_execution_gate
from .feature_engine import FeatureSnapshot


@dataclass(frozen=True)
class PredictionEvidence:
    prediction_id: str
    snapshot_id: str
    opportunity_id: str
    strategy_version: str
    model_version: str
    prediction_time: str
    target_definition_version: str
    horizon_definition_version: str
    prediction_type: str
    prediction_value: float | None
    uncertainty: float | None
    calibration_reference: str | None
    provenance: Mapping[str, str]


@dataclass(frozen=True)
class DecisionEligibility:
    eligible: bool
    reason: str
    snapshot_id: str
    prediction_id: str
    opportunity_id: str


@dataclass(frozen=True)
class AuthorizedTradeIntent:
    intent_id: str
    opportunity_id: str
    decision_id: str
    authorization_version: str
    authorized_risk: float
    issued_at: str


@dataclass(frozen=True)
class SelectedInstrument:
    selection_id: str
    intent_id: str
    instrument_id: str
    selection_version: str
    selected_at: str


@dataclass(frozen=True)
class OrderIntent:
    order_intent_id: str
    selection_id: str
    instrument_id: str
    side: str
    quantity: int
    intent_version: str
    idempotency_key: str
    created_at: str


@dataclass(frozen=True)
class ExecutionEvent:
    execution_event_id: str
    order_intent_id: str
    event_type: str
    event_time: str
    broker_reference: str | None = None
    filled_quantity: int = 0
    fill_price: float | None = None


@dataclass(frozen=True)
class PositionState:
    position_id: str
    instrument_id: str
    quantity: int
    average_price: float
    lifecycle_state: str
    source_execution_event_id: str


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    stage: str
    object_id: str
    parent_ids: tuple[str, ...]


@dataclass(frozen=True)
class E2ETrace:
    event: CanonicalMarketEvent
    snapshot: FeatureSnapshot
    prediction: PredictionEvidence | None
    edge: EdgeAssessment | None
    economics: EconomicAssessment | None
    decision: DecisionEligibility | None
    authorization: AuthorizedTradeIntent | None
    instrument: SelectedInstrument | None
    order: OrderIntent | None
    execution: ExecutionEvent | None
    position: PositionState | None
    audit: tuple[AuditRecord, ...]
    execution_gate: ExecutionGateDecision


class PredictionEngine(Protocol):
    def predict(self, snapshot: FeatureSnapshot) -> PredictionEvidence: ...


class FeatureBuilder(Protocol):
    def build(self, event: CanonicalMarketEvent) -> FeatureSnapshot: ...


class DecisionEngine(Protocol):
    def assess(
        self,
        snapshot: FeatureSnapshot,
        prediction: PredictionEvidence,
        edge: EdgeAssessment,
        economics: EconomicAssessment,
    ) -> DecisionEligibility: ...


class RiskAuthorizer(Protocol):
    def authorize(self, decision: DecisionEligibility) -> AuthorizedTradeIntent: ...


class InstrumentSelector(Protocol):
    def select(self, intent: AuthorizedTradeIntent) -> SelectedInstrument: ...


class OrderIntentFactory(Protocol):
    def create(self, instrument: SelectedInstrument) -> OrderIntent: ...


class ExecutionAdapter(Protocol):
    def submit(self, order: OrderIntent) -> ExecutionEvent: ...


class PositionProjector(Protocol):
    def project(self, event: ExecutionEvent) -> PositionState: ...


T = TypeVar("T")


class AuditLedger:
    """Append-only causal ledger for deterministic replay and audit."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, stage: str, object_id: str, *parent_ids: str) -> None:
        self._records.append(
            AuditRecord(len(self._records), stage, object_id, tuple(parent_ids))
        )

    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)


def run_e2e(
    event: CanonicalMarketEvent,
    *,
    feature_builder: FeatureBuilder,
    prediction_engine: PredictionEngine,
    edge_formula: EdgeFormula,
    decision_engine: DecisionEngine,
    risk_authorizer: RiskAuthorizer,
    instrument_selector: InstrumentSelector,
    order_factory: OrderIntentFactory,
    execution_adapter: ExecutionAdapter,
    position_projector: PositionProjector,
    execution_cost: float,
    minimum_net_value: float = 0.0,
    required_formula_ids: tuple[str, ...] = (),
) -> E2ETrace:
    """Run one candidate through the complete dependency graph.

    The orchestration is deliberately dependency-injected. It supplies no
    strategy formula, risk schedule, option-selection rule, quantity rule, or
    lifecycle parameter of its own.
    """
    audit = AuditLedger()
    audit.append("market_event", event.record_id)

    snapshot = feature_builder.build(event)
    audit.append("feature_snapshot", snapshot.snapshot_id, event.record_id)

    prediction = prediction_engine.predict(snapshot)
    audit.append("prediction", prediction.prediction_id, snapshot.snapshot_id)

    edge = evaluate_edge(snapshot, edge_formula)
    audit.append("edge", edge.opportunity_id, prediction.prediction_id, snapshot.snapshot_id)

    economics = evaluate_economics(
        edge,
        execution_cost=execution_cost,
        minimum_net_value=minimum_net_value,
    )
    audit.append("economics", edge.opportunity_id, edge.opportunity_id)

    decision = decision_engine.assess(snapshot, prediction, edge, economics)
    audit.append("decision", decision.opportunity_id, prediction.prediction_id)

    if not decision.eligible:
        return E2ETrace(
            event, snapshot, prediction, edge, economics, decision,
            None, None, None, None, None, audit.records(),
            evaluate_execution_gate(required_formula_ids),
        )

    gate = evaluate_execution_gate(required_formula_ids)
    if not gate.authorized:
        return E2ETrace(
            event, snapshot, prediction, edge, economics, decision,
            None, None, None, None, None, audit.records(), gate,
        )

    authorization = risk_authorizer.authorize(decision)
    audit.append("risk_authorization", authorization.intent_id, decision.opportunity_id)
    instrument = instrument_selector.select(authorization)
    audit.append("instrument", instrument.selection_id, authorization.intent_id)
    order = order_factory.create(instrument)
    audit.append("order_intent", order.order_intent_id, instrument.selection_id)
    execution = execution_adapter.submit(order)
    audit.append("execution_event", execution.execution_event_id, order.order_intent_id)
    position = position_projector.project(execution)
    audit.append("position", position.position_id, execution.execution_event_id)

    return E2ETrace(
        event, snapshot, prediction, edge, economics, decision,
        authorization, instrument, order, execution, position,
        audit.records(), gate,
    )
