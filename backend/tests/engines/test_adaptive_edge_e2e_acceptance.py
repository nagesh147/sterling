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

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_adapter import (
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
from app.engines.adaptive_edge.entry_decision import ConjunctionDecisionEngine, EntryDecisionEvidence
from app.engines.adaptive_edge.e2e_adapters import (
    BarFeatureBuilder,
    ComposedLifecycleEngine,
    ComposedOrderIntentFactory,
    ComposedRiskAuthorizer,
    ExplicitGrossEdge,
    IdentityPredictionBinder,
    InstrumentAwarePositionProjector,
    ListedInstrumentSelector,
)
from app.engines.adaptive_edge.instrument_selection import ListedOptionCandidate
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.e2e import (
    ExecutionMode,
    ReplayContext,
    run_e2e,
)


class MockBrokerTransport:
    def __init__(self) -> None:
        self.submitted_orders: list[CanonicalOrderIntent] = []

    def submit(self, intent: CanonicalOrderIntent) -> str:
        self.submitted_orders.append(intent)
        return f"BROKER-REF-{intent.order_intent_id}"


def _f110_engine() -> ConjunctionDecisionEngine:
    """Real F-110 conjunction. ConservativeEV is explicit, not inferred."""
    return ConjunctionDecisionEngine(
        EntryDecisionEvidence(
            option_type="CE",
            conservative_ev=80.0,
            directional_edge_ok=True,
            liquidity_ok=True,
            slippage_ok=True,
            risk_ok=True,
        )
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


def _param(name: str, value: float, units: str = "INR") -> ParameterMetadata:
    return ParameterMetadata(
        name=name,
        value=value,
        units=units,
        version="1.0.0",
        provenance="Master_Spec_v1.0_Sec31_Sec36",
        estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
        validation_status=ParameterValidationStatus.VALIDATED,
    )


def _listed_chain() -> tuple[ListedOptionCandidate, ...]:
    available = "2026-08-17T03:44:00+00:00"
    return (
        ListedOptionCandidate("NIFTY26AUG24600CE", "CE", 24600.0, "2026-08-27", 50.0, available),
        ListedOptionCandidate("NIFTY26AUG24400CE", "CE", 24400.0, "2026-08-27", 90.0, available),
        ListedOptionCandidate("NIFTY26AUG24500CE", "CE", 24500.0, "2026-08-27", 90.0, available),
        ListedOptionCandidate("NIFTY26AUG24500PE", "PE", 24500.0, "2026-08-27", 120.0, available),
    )


def _composed_execution():
    costs = ExecutionCostParameters(
        spread_cost=_param("spread_cost", 1.0),
        expected_slippage=_param("expected_slippage", 0.5),
        brokerage_per_unit=_param("brokerage_per_unit", 0.2),
        exchange_charges_per_unit=_param("exchange_charges_per_unit", 0.1),
        taxes_per_unit=_param("taxes_per_unit", 0.1),
        latency_cost_per_unit=_param("latency_cost_per_unit", 0.1),
    )
    risk_unit = calculate_risk_per_unit(100.0, 90.0, costs)
    auth = RiskAuthorization(
        opportunity_id="opp-e2e",
        authorized_risk=5000.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="risk-v1",
        issued_at="2026-08-17T03:45:00+00:00",
    )
    sizing = calculate_position_sizing(
        auth,
        risk_unit,
        SizingParameters(
            max_position_qty=_param("max_position_qty", 50.0, "contracts"),
            max_capital_allocation=_param("max_capital_allocation", 100_000.0, "INR"),
            lot_size=_param("lot_size", 25.0, "contracts"),
        ),
    )
    authorizer = ComposedRiskAuthorizer(auth)
    selector = ListedInstrumentSelector(_listed_chain(), option_type="CE")
    factory = ComposedOrderIntentFactory(
        sizing=sizing,
        created_at="2026-08-17T03:45:00+00:00",
        authorized_risk=auth.authorized_risk,
    )
    projector = InstrumentAwarePositionProjector("NIFTY26AUG24500CE", side="BUY")
    lifecycle = ComposedLifecycleEngine()
    return authorizer, selector, factory, projector, lifecycle, sizing.final_quantity


def _pending_fill(qty: int) -> BrokerExecutionEvent:
    return BrokerExecutionEvent(
        broker_event_id="pending",
        order_intent_id="pending",
        broker_status="FILLED",
        event_time="2026-08-17T09:15:02+00:00",
        filled_quantity=qty,
        fill_price=152.0,
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

    authorizer, selector, factory, projector, lifecycle, _qty = _composed_execution()
    trace = run_e2e(
        event,
        feature_builder=BarFeatureBuilder(),
        prediction_engine=IdentityPredictionBinder(),
        edge_formula=ExplicitGrossEdge(120.0),
        decision_engine=_f110_engine(),
        risk_authorizer=authorizer,
        instrument_selector=selector,
        order_factory=factory,
        execution_gateway=gateway,
        position_projector=projector,
        lifecycle_engine=lifecycle,
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

    authorizer, selector, factory, projector, lifecycle, _qty = _composed_execution()
    trace = run_e2e(
        event,
        feature_builder=BarFeatureBuilder(),
        prediction_engine=IdentityPredictionBinder(),
        edge_formula=ExplicitGrossEdge(None),  # Missing gross value!
        decision_engine=_f110_engine(),
        risk_authorizer=authorizer,
        instrument_selector=selector,
        order_factory=factory,
        execution_gateway=gateway,
        position_projector=projector,
        lifecycle_engine=lifecycle,
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
    authorizer, selector, factory, projector, lifecycle, qty = _composed_execution()

    trace = run_e2e(
        event,
        feature_builder=BarFeatureBuilder(),
        prediction_engine=IdentityPredictionBinder(),
        edge_formula=ExplicitGrossEdge(120.0),
        decision_engine=_f110_engine(),
        risk_authorizer=authorizer,
        instrument_selector=selector,
        order_factory=factory,
        execution_gateway=gateway,
        position_projector=projector,
        lifecycle_engine=lifecycle,
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
        broker_event=_pending_fill(qty),
    )

    assert trace.execution_gate.authorized is True
    assert trace.snapshot.values["close"] == 24510.0
    assert trace.prediction.prediction_value is None
    assert trace.prediction.provenance["binding"] == "identity-only"
    assert trace.edge.score == 0.0
    assert trace.decision.eligible is True
    assert trace.decision.reason == "entry_conjunction_passed"
    assert trace.authorization is not None
    assert trace.authorization.decision_id == trace.decision.decision_id
    assert trace.authorization.authorized_risk == 5000.0
    assert trace.instrument.instrument_id == "NIFTY26AUG24500CE"
    assert trace.instrument.intent_id == trace.authorization.intent_id
    assert trace.instrument.selection_version == "listed-v1"
    assert trace.order.quantity == qty
    assert trace.order.authorization_id == trace.instrument.intent_id
    assert len(transport.submitted_orders) == 1
    assert trace.execution.filled_quantity == qty
    assert trace.execution.fill_price == 152.0
    assert trace.execution.order_intent_id == trace.order.order_intent_id
    assert trace.position.lifecycle_state == "OPEN"
    assert trace.position.quantity == qty
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

    authorizer1, selector1, factory1, projector1, lifecycle1, qty = _composed_execution()
    authorizer2, selector2, factory2, projector2, lifecycle2, _ = _composed_execution()

    gateway1, _ = _setup_pipeline()
    trace1 = run_e2e(
        event,
        feature_builder=BarFeatureBuilder(),
        prediction_engine=IdentityPredictionBinder(),
        edge_formula=ExplicitGrossEdge(120.0),
        decision_engine=_f110_engine(),
        risk_authorizer=authorizer1,
        instrument_selector=selector1,
        order_factory=factory1,
        execution_gateway=gateway1,
        position_projector=projector1,
        lifecycle_engine=lifecycle1,
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
        broker_event=_pending_fill(qty),
        replay_context=replay_ctx,
    )

    gateway2, _ = _setup_pipeline()
    trace2 = run_e2e(
        event,
        feature_builder=BarFeatureBuilder(),
        prediction_engine=IdentityPredictionBinder(),
        edge_formula=ExplicitGrossEdge(120.0),
        decision_engine=_f110_engine(),
        risk_authorizer=authorizer2,
        instrument_selector=selector2,
        order_factory=factory2,
        execution_gateway=gateway2,
        position_projector=projector2,
        lifecycle_engine=lifecycle2,
        execution_cost=20.0,
        mode=ExecutionMode.SIMULATION,
        required_formula_ids=("F-004",),
        broker_event=_pending_fill(qty),
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
