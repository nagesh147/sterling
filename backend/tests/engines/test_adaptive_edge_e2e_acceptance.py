"""Acceptance tests for Adaptive Edge End-to-End Execution Path.

Enforces the 6 mandatory invariants:
T1: Production gate (Realistic input -> BLOCKED -> 0 broker submissions -> complete blocked trace)
T2: Causal integrity (available_at < event_time -> immediate rejection -> no downstream objects)
T3: Economic fail-closed (missing expected gross value -> ineligible -> no authorization -> no order)
T4: Authorized simulation (same canonical input in simulation mode -> full pipeline -> complete trace)
T5: Canonical replay (same input + same ReplayContext -> identical trace hash and audit sequence)
T6: Boundary bypass prevention (invoking OrderFactory/ExecutionGateway without authorization -> rejected)
"""
from __future__ import annotations

from dataclasses import dataclass
import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.edge import EdgeAssessment, EdgeFormula
from app.engines.adaptive_edge.economic import EconomicAssessment
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_adapter import (
    CanonicalExecutionEvent,
    CanonicalExecutionStatus,
    CanonicalOrderIntent,
    ExecutionAdapter,
)
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gate import (
    ExecutionBlockedError,
    ExecutionGateStatus,
)
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.feature_engine import (
    FeatureInput,
    FeatureSnapshot,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)
from app.engines.adaptive_edge.e2e import (
    AuthorizedTradeIntent,
    DecisionEligibility,
    ExecutionMode,
    LifecycleEvaluation,
    PositionState,
    PredictionEvidence,
    ReplayContext,
    SelectedInstrument,
    run_e2e,
)


class MockBrokerTransport:
    def __init__(self) -> None:
        self.submitted_orders: list[CanonicalOrderIntent] = []

    def submit(self, intent: CanonicalOrderIntent) -> str:
        self.submitted_orders.append(intent)
        return f"BROKER-REF-{intent.order_intent_id}"


class MockFeatureBuilder:
    def build(self, event: CanonicalMarketEvent) -> FeatureSnapshot:
        return build_feature_snapshot(
            snapshot_id=f"SNAP-{event.record_id}",
            strategy_version="v2.0",
            feature_set_version="fset-v1",
            observation_cutoff_time=event.available_at,
            decision_time=event.available_at,
            instrument_context=InstrumentContext(event.instrument_id),
            inputs=[
                FeatureInput("close", event.payload.get("close", 100.0), event.available_at, FeatureStatus.VALID),
                FeatureInput("volume", event.payload.get("volume", 1000.0), event.available_at, FeatureStatus.VALID),
            ],
        )


class MockPredictionEngine:
    def predict(self, snapshot: FeatureSnapshot) -> PredictionEvidence:
        return PredictionEvidence(
            prediction_id=f"PRED-{snapshot.snapshot_id}",
            snapshot_id=snapshot.snapshot_id,
            opportunity_id=f"OPP-{snapshot.snapshot_id}",
            strategy_version="v2.0",
            model_version="model-v1",
            prediction_time=snapshot.decision_time,
            target_definition_version="target-v1",
            horizon_definition_version="horizon-15m",
            prediction_type="CLASSIFICATION",
            prediction_value=0.75,
            uncertainty=0.05,
            calibration_reference="calib-v1",
            provenance={"model": "offline-linear"},
        )


@dataclass
class MockEdgeFormula:
    formula_id: str = "F-004"
    formula_version: str = "1.0"
    expected_gross: float | None = 120.0

    def evaluate(self, snapshot: FeatureSnapshot) -> EdgeAssessment:
        return EdgeAssessment(
            opportunity_id=f"OPP-{snapshot.snapshot_id}",
            score=0.8,
            confidence=0.9,
            expected_gross_value=self.expected_gross,
            formula_id=self.formula_id,
            formula_version=self.formula_version,
            inputs={"close": 100.0},
        )


class MockDecisionEngine:
    def assess(
        self,
        snapshot: FeatureSnapshot,
        prediction: PredictionEvidence,
        edge: EdgeAssessment,
        economics: EconomicAssessment,
    ) -> DecisionEligibility:
        return DecisionEligibility(
            eligible=economics.eligible,
            reason="economically_eligible" if economics.eligible else economics.reason,
            decision_id=f"DEC-{snapshot.snapshot_id}",
            snapshot_id=snapshot.snapshot_id,
            prediction_id=prediction.prediction_id,
            opportunity_id=prediction.opportunity_id,
        )


class MockRiskAuthorizer:
    def authorize(self, decision: DecisionEligibility) -> AuthorizedTradeIntent:
        return AuthorizedTradeIntent(
            intent_id=f"AUTH-{decision.decision_id}",
            opportunity_id=decision.opportunity_id,
            decision_id=decision.decision_id,
            authorization_version="risk-v1",
            authorized_risk=5000.0,
            issued_at="2026-08-17T09:15:00+00:00",
        )


class MockInstrumentSelector:
    def select(self, intent: AuthorizedTradeIntent) -> SelectedInstrument:
        return SelectedInstrument(
            selection_id=f"SEL-{intent.intent_id}",
            intent_id=intent.intent_id,
            instrument_id="NIFTY26AUG24500CE",
            selection_version="moneyness-v1",
            selected_at="2026-08-17T09:15:00+00:00",
        )


class MockOrderIntentFactory:
    def create(self, instrument: SelectedInstrument) -> CanonicalOrderIntent:
        return CanonicalOrderIntent(
            order_intent_id=f"ORDER-{instrument.selection_id}",
            selection_id=instrument.selection_id,
            instrument_id=instrument.instrument_id,
            side="BUY",
            quantity=50,
            intent_version="order-v1",
            idempotency_key=f"IDEM-{instrument.selection_id}",
            created_at="2026-08-17T09:15:00+00:00",
        )


class MockPositionProjector:
    def project(self, event: CanonicalExecutionEvent) -> PositionState:
        return PositionState(
            position_id=f"POS-{event.order_intent_id}",
            instrument_id="NIFTY26AUG24500CE",
            quantity=event.filled_quantity or 50,
            average_price=event.fill_price or 150.0,
            lifecycle_state="OPEN",
            source_execution_event_id=event.execution_event_id,
        )


class MockLifecycleEngine:
    def evaluate(self, position: PositionState, event: CanonicalMarketEvent) -> LifecycleEvaluation:
        return LifecycleEvaluation(
            evaluation_id=f"LIFE-{position.position_id}",
            position_id=position.position_id,
            lifecycle_version="life-v1",
            lifecycle_state="OPEN",
            protection_state="INITIAL_STOP_ACTIVE",
            action="HOLD",
            reason="within_protection_envelope",
            evaluated_at=event.available_at,
        )


def _make_realistic_event(record_id: str = "TD-BAR-001") -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id=record_id,
        event_type="bar",
        instrument_id="NIFTY 50",
        event_time="2026-08-17T09:15:00+00:00",
        available_at="2026-08-17T09:15:01+00:00",
        source="truedata",
        source_version="2.6",
        payload={
            "open": 24500.0,
            "high": 24520.0,
            "low": 24490.0,
            "close": 24510.0,
            "volume": 1500.0,
            "oi": 120000.0,
        },
        provenance={"provider": "TrueData", "feed": "live_feed_v1"},
    )


def _setup_pipeline(transport: MockBrokerTransport | None = None) -> tuple[ExecutionGateway, MockBrokerTransport]:
    trans = transport or MockBrokerTransport()
    gateway = ExecutionGateway(
        ExecutionAdapter(trans),
        BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )
    return gateway, trans


# --- T1: Production Gate ---
def test_t1_production_gate_blocks_and_submits_zero_orders():
    gateway, transport = _setup_pipeline()
    event = _make_realistic_event()

    trace = run_e2e(
        event,
        feature_builder=MockFeatureBuilder(),
        prediction_engine=MockPredictionEngine(),
        edge_formula=MockEdgeFormula(),
        decision_engine=MockDecisionEngine(),
        risk_authorizer=MockRiskAuthorizer(),
        instrument_selector=MockInstrumentSelector(),
        order_factory=MockOrderIntentFactory(),
        execution_gateway=gateway,
        position_projector=MockPositionProjector(),
        lifecycle_engine=MockLifecycleEngine(),
        execution_cost=20.0,
        mode=ExecutionMode.PRODUCTION,
    )

    assert trace.execution_gate.status is ExecutionGateStatus.BLOCKED
    assert trace.execution_gate.authorized is False
    assert len(transport.submitted_orders) == 0
    assert trace.order is None
    assert trace.execution is None
    assert trace.position is None
    assert trace.lifecycle is None
    assert trace.audit[-1].stage == "prediction"


# --- T2: Causal Integrity ---
def test_t2_causal_integrity_rejects_lookahead_events():
    gateway, transport = _setup_pipeline()

    # Event where available_at precedes event_time
    with pytest.raises(ValueError, match="available_at cannot precede event_time"):
        CanonicalMarketEvent(
            record_id="TD-LOOKAHEAD",
            event_type="bar",
            instrument_id="NIFTY 50",
            event_time="2026-08-17T09:15:00+00:00",
            available_at="2026-08-17T09:14:59+00:00",
            source="truedata",
            source_version="2.6",
            payload={"close": 24500.0},
        )
    assert len(transport.submitted_orders) == 0


# --- T3: Economic Fail-Closed ---
def test_t3_economic_fail_closed_missing_gross_value():
    gateway, transport = _setup_pipeline()
    event = _make_realistic_event()

    trace = run_e2e(
        event,
        feature_builder=MockFeatureBuilder(),
        prediction_engine=MockPredictionEngine(),
        edge_formula=MockEdgeFormula(expected_gross=None),  # Missing gross value!
        decision_engine=MockDecisionEngine(),
        risk_authorizer=MockRiskAuthorizer(),
        instrument_selector=MockInstrumentSelector(),
        order_factory=MockOrderIntentFactory(),
        execution_gateway=gateway,
        position_projector=MockPositionProjector(),
        lifecycle_engine=MockLifecycleEngine(),
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
    )

    assert trace.economics.eligible is False
    assert trace.economics.reason == "missing_expected_gross_value"
    assert trace.decision.eligible is False
    assert trace.authorization is None
    assert trace.order is None
    assert len(transport.submitted_orders) == 0


# --- T4: Authorized Simulation ---
def test_t4_authorized_simulation_completes_full_pipeline():
    gateway, transport = _setup_pipeline()
    event = _make_realistic_event()

    broker_fill = BrokerExecutionEvent(
        broker_event_id="BE-001",
        order_intent_id="ORDER-SEL-AUTH-DEC-SNAP-TD-BAR-001",
        broker_status="FILLED",
        event_time="2026-08-17T09:15:02+00:00",
        broker_reference="BROKER-REF-ORDER-SEL-AUTH-DEC-SNAP-TD-BAR-001",
        filled_quantity=50,
        fill_price=152.0,
    )

    trace = run_e2e(
        event,
        feature_builder=MockFeatureBuilder(),
        prediction_engine=MockPredictionEngine(),
        edge_formula=MockEdgeFormula(expected_gross=120.0),
        decision_engine=MockDecisionEngine(),
        risk_authorizer=MockRiskAuthorizer(),
        instrument_selector=MockInstrumentSelector(),
        order_factory=MockOrderIntentFactory(),
        execution_gateway=gateway,
        position_projector=MockPositionProjector(),
        lifecycle_engine=MockLifecycleEngine(),
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
        broker_event=broker_fill,
    )

    assert trace.execution_gate.authorized is True
    assert trace.decision.eligible is True
    assert trace.authorization is not None
    assert trace.instrument.instrument_id == "NIFTY26AUG24500CE"
    assert trace.order.quantity == 50
    assert len(transport.submitted_orders) == 1
    assert trace.execution.filled_quantity == 50
    assert trace.execution.fill_price == 152.0
    assert trace.position.lifecycle_state == "OPEN"
    assert trace.lifecycle.action == "HOLD"
    assert len(trace.audit) == 12


# --- T5: Canonical Replay ---
def test_t5_canonical_replay_produces_identical_hash_and_audit():
    event = _make_realistic_event()
    replay_ctx = ReplayContext(
        decision_time="2026-08-17T09:15:01+00:00",
        event_time="2026-08-17T09:15:00+00:00",
        sequence_seed=42,
    )

    broker_fill = BrokerExecutionEvent(
        broker_event_id="BE-001",
        order_intent_id="ORDER-SEL-AUTH-DEC-SNAP-TD-BAR-001",
        broker_status="FILLED",
        event_time="2026-08-17T09:15:02+00:00",
        broker_reference="BROKER-REF-ORDER-SEL-AUTH-DEC-SNAP-TD-BAR-001",
        filled_quantity=50,
        fill_price=152.0,
    )

    gateway1, _ = _setup_pipeline()
    trace1 = run_e2e(
        event,
        feature_builder=MockFeatureBuilder(),
        prediction_engine=MockPredictionEngine(),
        edge_formula=MockEdgeFormula(),
        decision_engine=MockDecisionEngine(),
        risk_authorizer=MockRiskAuthorizer(),
        instrument_selector=MockInstrumentSelector(),
        order_factory=MockOrderIntentFactory(),
        execution_gateway=gateway1,
        position_projector=MockPositionProjector(),
        lifecycle_engine=MockLifecycleEngine(),
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
        broker_event=broker_fill,
        replay_context=replay_ctx,
    )

    gateway2, _ = _setup_pipeline()
    trace2 = run_e2e(
        event,
        feature_builder=MockFeatureBuilder(),
        prediction_engine=MockPredictionEngine(),
        edge_formula=MockEdgeFormula(),
        decision_engine=MockDecisionEngine(),
        risk_authorizer=MockRiskAuthorizer(),
        instrument_selector=MockInstrumentSelector(),
        order_factory=MockOrderIntentFactory(),
        execution_gateway=gateway2,
        position_projector=MockPositionProjector(),
        lifecycle_engine=MockLifecycleEngine(),
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
        broker_event=broker_fill,
        replay_context=replay_ctx,
    )

    assert trace1.trace_hash == trace2.trace_hash
    assert trace1.audit == trace2.audit
    assert trace1.position == trace2.position
    assert trace1.lifecycle == trace2.lifecycle


# --- T6: Boundary Bypass Prevention ---
def test_t6_boundary_bypass_prevention_rejects_unauthorized_gateway_submission():
    gateway, transport = _setup_pipeline()
    intent = CanonicalOrderIntent(
        order_intent_id="DIRECT-ORDER-001",
        selection_id="SEL-001",
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
        quantity=50,
        intent_version="order-v1",
        idempotency_key="IDEM-DIRECT-001",
        created_at="2026-08-17T09:15:00+00:00",
    )

    # Calling submit without authorized formula context must be rejected
    with pytest.raises(ExecutionBlockedError):
        gateway.submit(intent)  # Defaults to REQUIRED_STRATEGY_FORMULAS which are LOCKED

    assert len(transport.submitted_orders) == 0
