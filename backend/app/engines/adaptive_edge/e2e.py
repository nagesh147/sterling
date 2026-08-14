"""End-to-end Adaptive Edge orchestration contracts.

This module composes canonical boundaries. It does not invent locked strategy
mathematics or lifecycle parameters. Submission and execution are separate
causal events: an order submission yields a broker reference; a broker event
is independently normalized into a canonical execution event.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .broker_event_mapper import BrokerExecutionEvent
from .edge import EdgeAssessment, EdgeFormula, evaluate_edge
from .economic import EconomicAssessment, evaluate_economics
from .event_boundary import CanonicalMarketEvent
from .execution_adapter import CanonicalExecutionEvent, CanonicalOrderIntent
from .execution_gateway import ExecutionGateway
from .execution_gate import ExecutionGateDecision, REQUIRED_STRATEGY_FORMULAS, evaluate_execution_gate
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
    decision_id: str
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
class PositionState:
    position_id: str
    instrument_id: str
    quantity: int
    average_price: float
    lifecycle_state: str
    source_execution_event_id: str


@dataclass(frozen=True)
class LifecycleEvaluation:
    evaluation_id: str
    position_id: str
    lifecycle_version: str
    lifecycle_state: str
    protection_state: str
    action: str
    reason: str
    evaluated_at: str


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
    order: CanonicalOrderIntent | None
    execution: CanonicalExecutionEvent | None
    position: PositionState | None
    lifecycle: LifecycleEvaluation | None
    audit: tuple[AuditRecord, ...]
    execution_gate: ExecutionGateDecision


class PredictionEngine(Protocol):
    def predict(self, snapshot: FeatureSnapshot) -> PredictionEvidence: ...


class FeatureBuilder(Protocol):
    def build(self, event: CanonicalMarketEvent) -> FeatureSnapshot: ...


class DecisionEngine(Protocol):
    def assess(self, snapshot: FeatureSnapshot, prediction: PredictionEvidence,
               edge: EdgeAssessment, economics: EconomicAssessment) -> DecisionEligibility: ...


class RiskAuthorizer(Protocol):
    def authorize(self, decision: DecisionEligibility) -> AuthorizedTradeIntent: ...


class InstrumentSelector(Protocol):
    def select(self, intent: AuthorizedTradeIntent) -> SelectedInstrument: ...


class OrderIntentFactory(Protocol):
    def create(self, instrument: SelectedInstrument) -> CanonicalOrderIntent: ...


class PositionProjector(Protocol):
    def project(self, event: CanonicalExecutionEvent) -> PositionState: ...


class LifecycleEngine(Protocol):
    def evaluate(self, position: PositionState, event: CanonicalMarketEvent) -> LifecycleEvaluation: ...


class AuditLedger:
    """Append-only causal ledger for deterministic replay and audit."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, stage: str, object_id: str, *parent_ids: str) -> None:
        self._records.append(AuditRecord(len(self._records), stage, object_id, tuple(parent_ids)))

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
    execution_gateway: ExecutionGateway,
    position_projector: PositionProjector,
    lifecycle_engine: LifecycleEngine,
    execution_cost: float,
    minimum_net_value: float = 0.0,
    required_formula_ids: tuple[str, ...] | None = None,
    broker_event: BrokerExecutionEvent | None = None,
) -> E2ETrace:
    """Run one candidate through every currently authorized layer.

    The execution gate is evaluated before any locked strategy formula is
    invoked. Unresolved mathematics therefore stop the path deterministically.
    """
    audit = AuditLedger()
    audit.append("market_event", event.record_id)

    snapshot = feature_builder.build(event)
    audit.append("feature_snapshot", snapshot.snapshot_id, event.record_id)

    prediction = prediction_engine.predict(snapshot)
    if prediction.snapshot_id != snapshot.snapshot_id:
        raise ValueError("prediction snapshot identity mismatch")
    if prediction.prediction_time != snapshot.decision_time:
        raise ValueError("prediction time must equal snapshot decision time")
    audit.append("prediction", prediction.prediction_id, snapshot.snapshot_id)

    formula_ids = REQUIRED_STRATEGY_FORMULAS if required_formula_ids is None else required_formula_ids
    gate = evaluate_execution_gate(formula_ids)
    if not gate.authorized:
        return E2ETrace(event, snapshot, prediction, None, None, None, None, None, None, None, None, None, audit.records(), gate)

    edge = evaluate_edge(snapshot, edge_formula)
    if edge.opportunity_id != prediction.opportunity_id:
        raise ValueError("edge opportunity identity mismatch")
    audit.append("edge", edge.opportunity_id, prediction.prediction_id, snapshot.snapshot_id)

    economics = evaluate_economics(edge, execution_cost=execution_cost, minimum_net_value=minimum_net_value)
    audit.append("economics", edge.opportunity_id, edge.opportunity_id)

    decision = decision_engine.assess(snapshot, prediction, edge, economics)
    if decision.snapshot_id != snapshot.snapshot_id or decision.prediction_id != prediction.prediction_id:
        raise ValueError("decision causal identity mismatch")
    audit.append("decision", decision.decision_id, prediction.prediction_id)

    if not decision.eligible:
        return E2ETrace(event, snapshot, prediction, edge, economics, decision, None, None, None, None, None, None, audit.records(), gate)

    authorization = risk_authorizer.authorize(decision)
    if authorization.decision_id != decision.decision_id:
        raise ValueError("authorization decision identity mismatch")
    audit.append("risk_authorization", authorization.intent_id, decision.decision_id)

    instrument = instrument_selector.select(authorization)
    if instrument.intent_id != authorization.intent_id:
        raise ValueError("instrument authorization identity mismatch")
    audit.append("instrument", instrument.selection_id, authorization.intent_id)

    order = order_factory.create(instrument)
    if order.selection_id != instrument.selection_id or order.instrument_id != instrument.instrument_id:
        raise ValueError("order instrument identity mismatch")
    if order.quantity <= 0:
        raise ValueError("order quantity must be positive")
    if not order.idempotency_key:
        raise ValueError("order intent requires idempotency key")
    audit.append("order_intent", order.order_intent_id, instrument.selection_id)

    execution_gateway.submit(order)
    if broker_event is None:
        raise ValueError("broker execution event is required; submission is not execution")

    execution = execution_gateway.receive(broker_event)
    if execution.order_intent_id != order.order_intent_id:
        raise ValueError("execution order identity mismatch")
    audit.append("execution_event", execution.execution_event_id, order.order_intent_id)

    position = position_projector.project(execution)
    if position.source_execution_event_id != execution.execution_event_id:
        raise ValueError("position execution identity mismatch")
    audit.append("position", position.position_id, execution.execution_event_id)

    lifecycle = lifecycle_engine.evaluate(position, event)
    if lifecycle.position_id != position.position_id:
        raise ValueError("lifecycle position identity mismatch")
    audit.append("lifecycle", lifecycle.evaluation_id, position.position_id)

    return E2ETrace(event, snapshot, prediction, edge, economics, decision, authorization,
                    instrument, order, execution, position, lifecycle, audit.records(), gate)
