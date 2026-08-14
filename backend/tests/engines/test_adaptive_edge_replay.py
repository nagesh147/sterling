from dataclasses import dataclass
from typing import Mapping

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.edge import EdgeAssessment, EdgeFormula
from app.engines.adaptive_edge.economic import EconomicAssessment
from app.engines.adaptive_edge.e2e import (
    AuditRecord,
    AuthorizedTradeIntent,
    DecisionEligibility,
    PredictionEvidence,
    SelectedInstrument,
    run_e2e,
)
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_adapter import (
    CanonicalExecutionEvent,
    CanonicalExecutionStatus,
    CanonicalOrderIntent,
    ExecutionAdapter,
)
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.feature_engine import (
    FeatureInput,
    FeatureSnapshot,
    InstrumentContext,
    build_feature_snapshot,
)
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaDefinition, FormulaStatus
from app.engines.adaptive_edge.lifecycle_engine import A126LifecycleEngine, HorizonState
from app.engines.adaptive_edge.position_projector import (
    DeterministicPositionProjector,
    PositionInvariantError,
)
from app.engines.adaptive_edge.replay import ReplayResult, replay_trace, validate_audit_chain


class MockFeatureBuilder:
    def build(self, event: CanonicalMarketEvent) -> FeatureSnapshot:
        return build_feature_snapshot(
            snapshot_id="snap-1",
            strategy_version="v1",
            feature_set_version="v1",
            observation_cutoff_time=event.available_at,
            decision_time=event.available_at,
            instrument_context=InstrumentContext(event.instrument_id),
            inputs=[FeatureInput("px", event.payload["price"], event.available_at)],
        )


class MockPredictionEngine:
    def predict(self, snapshot: FeatureSnapshot) -> PredictionEvidence:
        return PredictionEvidence(
            prediction_id="pred-1",
            snapshot_id=snapshot.snapshot_id,
            opportunity_id="opp-1",
            strategy_version="v1",
            model_version="v1",
            prediction_time=snapshot.decision_time,
            target_definition_version="v1",
            horizon_definition_version="v1",
            prediction_type="DIRECTIONAL",
            prediction_value=0.85,
            uncertainty=0.10,
            calibration_reference="calib-1",
            provenance={"source": "mock"},
        )


@dataclass
class MockEdgeFormula:
    formula_id: str = "F-102"
    formula_version: str = "1.0"

    def evaluate(self, snapshot: FeatureSnapshot) -> EdgeAssessment:
        return EdgeAssessment(
            opportunity_id="opp-1",
            score=0.8,
            confidence=0.9,
            expected_gross_value=100.0,
            formula_id=self.formula_id,
            formula_version=self.formula_version,
            inputs={"px": 100.0},
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
            eligible=True,
            reason="passed_edge_and_economics",
            decision_id="dec-1",
            snapshot_id=snapshot.snapshot_id,
            prediction_id=prediction.prediction_id,
            opportunity_id=prediction.opportunity_id,
        )


class MockRiskAuthorizer:
    def authorize(self, decision: DecisionEligibility) -> AuthorizedTradeIntent:
        return AuthorizedTradeIntent(
            intent_id="auth-1",
            opportunity_id=decision.opportunity_id,
            decision_id=decision.decision_id,
            authorization_version="v1",
            authorized_risk=500.0,
            issued_at="2026-08-14T03:45:00+00:00",
        )


class MockInstrumentSelector:
    def select(self, intent: AuthorizedTradeIntent) -> SelectedInstrument:
        return SelectedInstrument(
            selection_id="sel-1",
            intent_id=intent.intent_id,
            instrument_id="NIFTY-CE",
            selection_version="v1",
            selected_at="2026-08-14T03:45:00+00:00",
        )


class MockOrderFactory:
    def create(self, instrument: SelectedInstrument) -> CanonicalOrderIntent:
        return CanonicalOrderIntent(
            order_intent_id="oi-1",
            selection_id=instrument.selection_id,
            instrument_id=instrument.instrument_id,
            side="BUY",
            quantity=50,
            intent_version="v1",
            idempotency_key="idem-1",
            created_at="2026-08-14T03:45:00+00:00",
        )


@dataclass
class MockTransport:
    def submit(self, intent: CanonicalOrderIntent) -> str:
        return f"broker-ord-{intent.order_intent_id}"


def make_market_event() -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id="evt-1",
        event_type="trade",
        instrument_id="NIFTY-CE",
        event_time="2026-08-14T03:45:00+00:00",
        available_at="2026-08-14T03:45:00+00:00",
        source="truedata",
        source_version="v1",
        payload={"price": 100.0},
    )


def test_e2e_trace_stops_at_gate_when_formulas_locked():
    event = make_market_event()
    gateway = ExecutionGateway(
        ExecutionAdapter(MockTransport()),
        BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE")
    lifecycle = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)

    trace = run_e2e(
        event,
        feature_builder=MockFeatureBuilder(),
        prediction_engine=MockPredictionEngine(),
        edge_formula=MockEdgeFormula(),
        decision_engine=MockDecisionEngine(),
        risk_authorizer=MockRiskAuthorizer(),
        instrument_selector=MockInstrumentSelector(),
        order_factory=MockOrderFactory(),
        execution_gateway=gateway,
        position_projector=projector,
        lifecycle_engine=lifecycle,
        execution_cost=10.0,
    )

    assert trace.execution_gate.authorized is False
    assert "F-101" in trace.execution_gate.blocking_formulas
    assert trace.order is None
    assert trace.execution is None
    assert trace.position is None
    assert trace.lifecycle is None

    # Replay validation of the causal prefix
    replay = replay_trace(trace)
    assert replay.deterministic is True
    assert replay.stages == ("market_event", "feature_snapshot", "prediction")


def test_e2e_trace_replays_identically_across_multiple_runs():
    event = make_market_event()
    broker_event = BrokerExecutionEvent(
        broker_event_id="be-1",
        order_intent_id="oi-1",
        broker_status="COMPLETE",
        event_time="2026-08-14T03:45:01+00:00",
        filled_quantity=50,
        fill_price=100.0,
    )

    original_f102 = FORMULAS["F-102"]
    try:
        FORMULAS["F-102"] = FormulaDefinition("F-102", "1.0", "Edge / prediction score", FormulaStatus.IMPLEMENTED, "score", "test")

        # Run 1
        g1 = ExecutionGateway(ExecutionAdapter(MockTransport()), BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}), ExecutionEventRegistry())
        p1 = DeterministicPositionProjector("pos-1", "NIFTY-CE")
        l1 = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
        trace1 = run_e2e(
            event, feature_builder=MockFeatureBuilder(), prediction_engine=MockPredictionEngine(),
            edge_formula=MockEdgeFormula(), decision_engine=MockDecisionEngine(),
            risk_authorizer=MockRiskAuthorizer(), instrument_selector=MockInstrumentSelector(),
            order_factory=MockOrderFactory(), execution_gateway=g1, position_projector=p1,
            lifecycle_engine=l1, execution_cost=10.0, required_formula_ids=(), broker_event=broker_event,
        )

        # Run 2 (identical inputs)
        g2 = ExecutionGateway(ExecutionAdapter(MockTransport()), BrokerEventMapper({"COMPLETE": CanonicalExecutionStatus.FILLED}), ExecutionEventRegistry())
        p2 = DeterministicPositionProjector("pos-1", "NIFTY-CE")
        l2 = A126LifecycleEngine("pos-1", initial_horizon=HorizonState.IMPULSE)
        trace2 = run_e2e(
            event, feature_builder=MockFeatureBuilder(), prediction_engine=MockPredictionEngine(),
            edge_formula=MockEdgeFormula(), decision_engine=MockDecisionEngine(),
            risk_authorizer=MockRiskAuthorizer(), instrument_selector=MockInstrumentSelector(),
            order_factory=MockOrderFactory(), execution_gateway=g2, position_projector=p2,
            lifecycle_engine=l2, execution_cost=10.0, required_formula_ids=(), broker_event=broker_event,
        )

        replay1 = replay_trace(trace1)
        replay2 = replay_trace(trace2)

        assert replay1.deterministic is True
        assert replay2.deterministic is True
        assert replay1 == replay2
        assert trace1.position == trace2.position
        assert trace1.lifecycle == trace2.lifecycle
    finally:
        FORMULAS["F-102"] = original_f102


def test_corrupted_stage_order_fails_replay():
    corrupted_records = [
        AuditRecord(0, "market_event", "e1", ()),
        AuditRecord(1, "prediction", "p1", ("e1",)),  # Skipped feature_snapshot
    ]
    result = validate_audit_chain(corrupted_records)
    assert result.deterministic is False
    assert result.reason == "invalid_causal_stage_order"


def test_corrupted_sequence_index_fails_replay():
    corrupted_records = [
        AuditRecord(0, "market_event", "e1", ()),
        AuditRecord(3, "feature_snapshot", "s1", ("e1",)),  # Jumped from 0 to 3
    ]
    result = validate_audit_chain(corrupted_records)
    assert result.deterministic is False
    assert result.reason == "non_contiguous_audit_sequence"


def test_corrupted_parent_reference_fails_replay():
    corrupted_records = [
        AuditRecord(0, "market_event", "e1", ()),
        AuditRecord(1, "feature_snapshot", "s1", ("wrong-parent-id",)),
    ]
    result = validate_audit_chain(corrupted_records)
    assert result.deterministic is False
    assert result.reason == "broken_parent_reference"


def test_corrupted_position_quantity_is_rejected():
    projector = DeterministicPositionProjector("pos-1", "NIFTY-CE")
    # Corrupted non-positive fill quantity
    bad_event = CanonicalExecutionEvent(
        execution_event_id="ex-1",
        order_intent_id="oi-1",
        event_type=CanonicalExecutionStatus.FILLED,
        event_time="2026-08-14T03:45:00+00:00",
        filled_quantity=-10,  # Negative quantity
        fill_price=100.0,
    )
    with pytest.raises(ValueError, match="filled_quantity cannot be negative"):
        projector.project(bad_event)


def test_corrupted_fill_price_is_rejected():
    bad_event = CanonicalExecutionEvent(
        execution_event_id="ex-1",
        order_intent_id="oi-1",
        event_type=CanonicalExecutionStatus.FILLED,
        event_time="2026-08-14T03:45:00+00:00",
        filled_quantity=10,
        fill_price=None,  # Missing fill price on fill event
    )
    with pytest.raises(ValueError, match="fill events require positive quantity and fill_price"):
        bad_event.validate()
