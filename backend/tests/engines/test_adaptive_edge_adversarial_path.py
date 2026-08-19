"""Adversarial fail-closed tests on the composed Adaptive Edge path.

The system must not invent fills, look ahead, or submit in production.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerExecutionEvent
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.e2e import SelectedInstrument
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus
from app.engines.adaptive_edge.execution_gate import (
    ExecutionBlockedError,
    evaluate_bid_ask_spread_gate,
    evaluate_execution_gate,
)
from app.engines.adaptive_edge.execution_path import AdaptiveEdgeExecutionPath
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.order_intent import CanonicalOrderIntentFactory, OrderIntentError
from app.engines.adaptive_edge.position_lifecycle import ManagedPosition, PostExitError
from app.engines.adaptive_edge.protection import ProtectionPolicy
from app.engines.adaptive_edge.replay import CanonicalEventSequence
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    PositionSizingAssessment,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


CREATED_AT = "2026-08-17T03:45:00+00:00"


class RecordingTransport:
    def __init__(self) -> None:
        self.submissions: list = []
        self.fail_with: Exception | None = None

    def submit(self, intent):
        if self.fail_with is not None:
            raise self.fail_with
        self.submissions.append(intent)
        return f"BROKER-{intent.order_intent_id}"


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


def _auth_and_sizing(*, authorized_risk: float = 5000.0, state: RiskState = RiskState.AUTHORIZED):
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
        opportunity_id="AUTH-1",
        authorized_risk=authorized_risk,
        risk_state=state,
        policy_version="risk-v1",
        issued_at=CREATED_AT,
    )
    if state is RiskState.AUTHORIZED and authorized_risk > 0:
        sizing = calculate_position_sizing(
            auth,
            risk_unit,
            SizingParameters(
                max_position_qty=_param("max_position_qty", 100.0, "contracts"),
                max_capital_allocation=_param("max_capital_allocation", 100_000.0, "INR"),
                lot_size=_param("lot_size", 25.0, "contracts"),
            ),
        )
    else:
        sizing = None
    return auth, sizing


def _instrument(auth_id: str = "AUTH-1") -> SelectedInstrument:
    return SelectedInstrument(
        selection_id=f"SEL-{auth_id}",
        intent_id=auth_id,
        instrument_id="NIFTY26AUG24500CE",
        selection_version="adv-v1",
        selected_at=CREATED_AT,
    )


def _bar(record_id: str, ts: str, close: float) -> CanonicalMarketEvent:
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


def test_naive_and_lookahead_timestamps_fail_closed():
    with pytest.raises(ValueError, match="timezone"):
        CanonicalMarketEvent(
            record_id="B1",
            event_type="bar",
            instrument_id="NIFTY-I",
            event_time="2026-08-17T03:45:00",
            available_at="2026-08-17T03:45:00",
            source="truedata",
            source_version="2.6",
            payload={"close": 1.0},
        )
    with pytest.raises(ValueError, match="available_at cannot precede event_time"):
        CanonicalMarketEvent(
            record_id="B2",
            event_type="bar",
            instrument_id="NIFTY-I",
            event_time="2026-08-17T03:46:00+00:00",
            available_at="2026-08-17T03:45:00+00:00",
            source="truedata",
            source_version="2.6",
            payload={"close": 1.0},
        )


def test_duplicate_and_shuffled_bars_do_not_change_sequence_hash():
    a = _bar("B1", "2026-08-17T03:45:00+00:00", 100.0)
    b = _bar("B2", "2026-08-17T03:46:00+00:00", 101.0)
    c = _bar("B3", "2026-08-17T03:47:00+00:00", 102.0)
    h1 = CanonicalEventSequence.from_events([a, b, c]).sequence_hash
    h2 = CanonicalEventSequence.from_events([c, a, b, a]).sequence_hash
    assert h1 == h2


def test_rejected_broker_event_does_not_open_quantity():
    auth, sizing = _auth_and_sizing()
    transport = RecordingTransport()
    path = AdaptiveEdgeExecutionPath(transport=transport, formula_ids=("F-004",))
    intent = CanonicalOrderIntentFactory(
        authorization=auth, sizing=sizing, side="BUY", created_at=CREATED_AT
    ).create(_instrument())
    path.submit(intent)
    step = path.receive_and_project(
        BrokerExecutionEvent(
            broker_event_id="BE-REJ",
            order_intent_id=intent.order_intent_id,
            broker_status="REJECTED",
            event_time="2026-08-17T03:45:02+00:00",
        ),
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
    )
    assert step.execution.event_type is CanonicalExecutionStatus.REJECTED
    assert step.position.quantity == 0
    assert step.position.lifecycle_state == "FLAT"


def test_zero_risk_budget_cannot_create_an_order():
    auth, _ = _auth_and_sizing(authorized_risk=0.0)
    sizing = calculate_position_sizing(
        auth,
        calculate_risk_per_unit(
            100.0,
            90.0,
            ExecutionCostParameters(
                spread_cost=_param("spread_cost", 1.0),
                expected_slippage=_param("expected_slippage", 0.5),
                brokerage_per_unit=_param("brokerage_per_unit", 0.2),
                exchange_charges_per_unit=_param("exchange_charges_per_unit", 0.1),
                taxes_per_unit=_param("taxes_per_unit", 0.1),
                latency_cost_per_unit=_param("latency_cost_per_unit", 0.1),
            ),
        ),
        SizingParameters(
            max_position_qty=_param("max_position_qty", 100.0, "contracts"),
            max_capital_allocation=_param("max_capital_allocation", 100_000.0, "INR"),
            lot_size=_param("lot_size", 25.0, "contracts"),
        ),
    )
    assert sizing.final_quantity == 0
    with pytest.raises(OrderIntentError, match="sizing"):
        CanonicalOrderIntentFactory(
            authorization=auth, sizing=sizing, side="BUY", created_at=CREATED_AT
        )


def test_unauthorized_state_cannot_build_intent():
    auth, _ = _auth_and_sizing(state=RiskState.UNAUTHORIZED)
    dummy = PositionSizingAssessment(
        target_quantity_unconstrained=50,
        target_quantity_constrained=50,
        final_quantity=50,
        gross_authorized_risk=100.0,
        effective_authorized_risk=120.0,
        authorized_risk_budget=5000.0,
        valid=True,
    )
    with pytest.raises(OrderIntentError, match="unauthorized"):
        CanonicalOrderIntentFactory(
            authorization=auth, sizing=dummy, side="BUY", created_at=CREATED_AT
        )


def test_transport_failure_does_not_record_a_broker_order():
    auth, sizing = _auth_and_sizing()
    transport = RecordingTransport()
    transport.fail_with = TimeoutError("gateway timeout")
    path = AdaptiveEdgeExecutionPath(transport=transport, formula_ids=("F-004",))
    intent = CanonicalOrderIntentFactory(
        authorization=auth, sizing=sizing, side="BUY", created_at=CREATED_AT
    ).create(_instrument())
    with pytest.raises(TimeoutError):
        path.submit(intent)
    assert transport.submissions == []


def test_wide_and_missing_spreads_fail_closed():
    missing = evaluate_bid_ask_spread_gate(bid=0.0, ask=0.0)
    assert missing.authorized is False
    wide = evaluate_bid_ask_spread_gate(bid=100.0, ask=120.0, max_spread_pct=3.0, max_spread_pts=3.0)
    assert wide.authorized is False
    ok = evaluate_bid_ask_spread_gate(bid=100.0, ask=100.5)
    assert ok.authorized is True


def test_production_gate_still_blocks_the_composed_path():
    assert evaluate_execution_gate().authorized is False
    auth, sizing = _auth_and_sizing()
    path = AdaptiveEdgeExecutionPath(transport=RecordingTransport(), formula_ids=None)
    intent = CanonicalOrderIntentFactory(
        authorization=auth, sizing=sizing, side="BUY", created_at=CREATED_AT
    ).create(_instrument())
    with pytest.raises(ExecutionBlockedError):
        path.submit(intent)
    assert FORMULAS["F-113"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED


def test_cannot_flatten_or_reuse_authorization_without_a_finalized_exit():
    auth, sizing = _auth_and_sizing()
    transport = RecordingTransport()
    path = AdaptiveEdgeExecutionPath(transport=transport, formula_ids=("F-004",))
    executed = path.submit_and_project(
        instrument=_instrument(),
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
        broker_event=BrokerExecutionEvent(
            broker_event_id="pending",
            order_intent_id="pending",
            broker_status="FILLED",
            event_time="2026-08-17T03:45:02+00:00",
            filled_quantity=sizing.final_quantity,
            fill_price=150.0,
        ),
        risk_boundary=140.0,
    )
    managed = ManagedPosition.from_execution(
        executed,
        policy=ProtectionPolicy("ADV", protective_stop_points=10.0),
    )
    with pytest.raises(PostExitError, match="outcome not finalized"):
        managed.flatten(path, fill_price=150.0, event_time="2026-08-17T03:46:00+00:00")
    managed.on_mark(140.0, "2026-08-17T03:46:00+00:00")
    managed.flatten(path, fill_price=140.0, event_time="2026-08-17T03:46:01+00:00")
    with pytest.raises(PostExitError, match="authorization cannot be reused"):
        managed.assert_independent_opportunity("AUTH-1")
