"""Replay and audit-chain tests. Do not mutate the formula registry."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerEventMapper, BrokerExecutionEvent
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.e2e import AuditRecord, ExecutionMode, run_e2e
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
from app.engines.adaptive_edge.entry_decision import ConjunctionDecisionEngine, EntryDecisionEvidence
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_adapter import (
    CanonicalExecutionEvent,
    CanonicalExecutionStatus,
    CanonicalOrderIntent,
    ExecutionAdapter,
)
from app.engines.adaptive_edge.execution_event_registry import ExecutionEventRegistry
from app.engines.adaptive_edge.execution_gateway import ExecutionGateway
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.instrument_selection import ListedOptionCandidate
from app.engines.adaptive_edge.position_projector import DeterministicPositionProjector
from app.engines.adaptive_edge.replay import replay_trace, validate_audit_chain
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


@dataclass
class MockTransport:
    def submit(self, intent: CanonicalOrderIntent) -> str:
        return f"broker-ord-{intent.order_intent_id}"


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
    available = "2026-08-14T03:44:00+00:00"
    return (
        ListedOptionCandidate("NIFTY26AUG24600CE", "CE", 24600.0, "2026-08-27", 50.0, available),
        ListedOptionCandidate("NIFTY26AUG24400CE", "CE", 24400.0, "2026-08-27", 90.0, available),
        ListedOptionCandidate("NIFTY26AUG24500CE", "CE", 24500.0, "2026-08-27", 90.0, available),
        ListedOptionCandidate("NIFTY26AUG24500PE", "PE", 24500.0, "2026-08-27", 120.0, available),
    )


def _composed_stack():
    costs = ExecutionCostParameters(
        spread_cost=_param("spread_cost", 1.0),
        expected_slippage=_param("expected_slippage", 0.5),
        brokerage_per_unit=_param("brokerage_per_unit", 0.2),
        exchange_charges_per_unit=_param("exchange_charges_per_unit", 0.1),
        taxes_per_unit=_param("taxes_per_unit", 0.1),
        latency_cost_per_unit=_param("latency_cost_per_unit", 0.1),
    )
    auth = RiskAuthorization(
        opportunity_id="opp-replay",
        authorized_risk=5000.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="risk-v1",
        issued_at="2026-08-14T03:45:00+00:00",
    )
    sizing = calculate_position_sizing(
        auth,
        calculate_risk_per_unit(100.0, 90.0, costs),
        SizingParameters(
            max_position_qty=_param("max_position_qty", 50.0, "contracts"),
            max_capital_allocation=_param("max_capital_allocation", 100_000.0, "INR"),
            lot_size=_param("lot_size", 25.0, "contracts"),
        ),
    )
    return (
        ComposedRiskAuthorizer(auth),
        ListedInstrumentSelector(_listed_chain(), option_type="CE"),
        ComposedOrderIntentFactory(
            sizing=sizing,
            created_at="2026-08-14T03:45:00+00:00",
            authorized_risk=auth.authorized_risk,
        ),
        InstrumentAwarePositionProjector("NIFTY26AUG24500CE", side="BUY"),
        ComposedLifecycleEngine(),
        sizing.final_quantity,
    )


def _f110() -> ConjunctionDecisionEngine:
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


def make_market_event() -> CanonicalMarketEvent:
    return CanonicalMarketEvent(
        record_id="evt-1",
        event_type="bar",
        instrument_id="NIFTY 50",
        event_time="2026-08-14T03:45:00+00:00",
        available_at="2026-08-14T03:45:00+00:00",
        source="truedata",
        source_version="v1",
        payload={"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1500.0},
    )


def _run_composed(*, required_formula_ids: tuple[str, ...], broker_event=None):
    authorizer, selector, factory, projector, lifecycle, qty = _composed_stack()
    gateway = ExecutionGateway(
        ExecutionAdapter(MockTransport()),
        BrokerEventMapper({"FILLED": CanonicalExecutionStatus.FILLED, "COMPLETE": CanonicalExecutionStatus.FILLED}),
        ExecutionEventRegistry(),
    )
    if broker_event is None and required_formula_ids == ("F-004",):
        broker_event = BrokerExecutionEvent(
            broker_event_id="pending",
            order_intent_id="pending",
            broker_status="FILLED",
            event_time="2026-08-14T03:45:01+00:00",
            filled_quantity=qty,
            fill_price=100.0,
        )
    return run_e2e(
        make_market_event(),
        feature_builder=BarFeatureBuilder(),
        prediction_engine=IdentityPredictionBinder(),
        edge_formula=ExplicitGrossEdge(100.0),
        decision_engine=_f110(),
        risk_authorizer=authorizer,
        instrument_selector=selector,
        order_factory=factory,
        execution_gateway=gateway,
        position_projector=projector,
        lifecycle_engine=lifecycle,
        execution_cost=10.0,
        required_formula_ids=required_formula_ids,
        broker_event=broker_event,
        mode=ExecutionMode.SIMULATION,
    ), qty


def test_e2e_trace_stops_at_gate_when_formulas_locked():
    trace, _qty = _run_composed(required_formula_ids=("F-999",))

    assert trace.execution_gate.authorized is False
    assert "F-999" in trace.execution_gate.blocking_formulas
    assert trace.order is None
    assert trace.execution is None
    assert trace.position is None
    assert trace.lifecycle is None
    assert FORMULAS["F-102"].status is FormulaStatus.LOCKED

    replay = replay_trace(trace)
    assert replay.deterministic is True
    assert replay.stages == ("market_event", "feature_snapshot", "prediction")


def test_e2e_trace_replays_identically_without_unlocking_f102():
    assert FORMULAS["F-102"].status is FormulaStatus.LOCKED
    trace1, _qty = _run_composed(required_formula_ids=("F-004",))
    trace2, _ = _run_composed(required_formula_ids=("F-004",))

    replay1 = replay_trace(trace1)
    replay2 = replay_trace(trace2)

    assert replay1.deterministic is True
    assert replay2.deterministic is True
    assert replay1 == replay2
    assert trace1.trace_hash == trace2.trace_hash
    assert trace1.position == trace2.position
    assert trace1.lifecycle == trace2.lifecycle
    assert trace1.prediction.prediction_value is None
    assert FORMULAS["F-102"].status is FormulaStatus.LOCKED


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
