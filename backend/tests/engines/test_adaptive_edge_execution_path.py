"""Integration tests for the Adaptive Edge execution path.

Closes the architectural gap:

    SelectedInstrument
        → CanonicalOrderIntent
        → ExecutionGateway
        → BrokerEvent
        → CanonicalExecutionEvent
        → PositionState

This is composition, not new strategy mathematics. Production remains
fail-closed: F-101..F-114 stay LOCKED and the gateway submits 0 orders.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.broker_event_mapper import (
    DEFAULT_BROKER_STATUS_MAP,
    BrokerExecutionEvent,
)
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.e2e import (
    AuthorizedTradeIntent,
    ReplayContext,
    SelectedInstrument,
)
from app.engines.adaptive_edge.execution_adapter import CanonicalExecutionStatus
from app.engines.adaptive_edge.execution_gate import ExecutionBlockedError
from app.engines.adaptive_edge.execution_path import AdaptiveEdgeExecutionPath
from app.engines.adaptive_edge.order_intent import (
    CanonicalOrderIntentFactory,
    OrderIntentError,
)
from app.engines.adaptive_edge.position_projector import PositionInvariantError
from app.engines.adaptive_edge.risk_sizing import (
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    PositionSizingAssessment,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
    ExecutionCostParameters,
)


CREATED_AT = "2026-08-17T03:45:00+00:00"  # 09:15 IST, before A126 cutoff


class RecordingTransport:
    def __init__(self) -> None:
        self.submissions: list = []

    def submit(self, intent) -> str:
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


def _sizing(
    *,
    authorized_risk: float = 5000.0,
    entry_price: float = 100.0,
    initial_stop: float = 90.0,
    max_qty: float = 500.0,
    max_cap: float = 100_000.0,
    lot_size: float = 25.0,
    risk_state: RiskState = RiskState.AUTHORIZED,
    opportunity_id: str = "AUTH-1",
) -> tuple[RiskAuthorization, PositionSizingAssessment]:
    costs = ExecutionCostParameters(
        spread_cost=_param("spread_cost", 1.0),
        expected_slippage=_param("expected_slippage", 0.5),
        brokerage_per_unit=_param("brokerage_per_unit", 0.2),
        exchange_charges_per_unit=_param("exchange_charges_per_unit", 0.1),
        taxes_per_unit=_param("taxes_per_unit", 0.1),
        latency_cost_per_unit=_param("latency_cost_per_unit", 0.1),
    )
    risk_unit = calculate_risk_per_unit(entry_price, initial_stop, costs)
    auth = RiskAuthorization(
        opportunity_id=opportunity_id,
        authorized_risk=authorized_risk,
        risk_state=risk_state,
        policy_version="risk-v1",
        issued_at=CREATED_AT,
    )
    sizing = calculate_position_sizing(
        auth,
        risk_unit,
        SizingParameters(
            max_position_qty=_param("max_position_qty", max_qty, "contracts"),
            max_capital_allocation=_param("max_capital_allocation", max_cap, "INR"),
            lot_size=_param("lot_size", lot_size, "contracts"),
        ),
    )
    return auth, sizing


def _instrument(auth_id: str = "AUTH-1", instrument_id: str = "NIFTY26AUG24500CE") -> SelectedInstrument:
    return SelectedInstrument(
        selection_id=f"SEL-{auth_id}",
        intent_id=auth_id,
        instrument_id=instrument_id,
        selection_version="f109-research-v1",
        selected_at=CREATED_AT,
    )


def _authorized_trade(intent_id: str = "AUTH-1") -> AuthorizedTradeIntent:
    return AuthorizedTradeIntent(
        intent_id=intent_id,
        opportunity_id="OPP-1",
        decision_id="DEC-1",
        authorization_version="risk-v1",
        authorized_risk=5000.0,
        issued_at=CREATED_AT,
    )


def _path(*, formula_ids: tuple[str, ...] | None = ("F-004",)) -> tuple[AdaptiveEdgeExecutionPath, RecordingTransport]:
    transport = RecordingTransport()
    path = AdaptiveEdgeExecutionPath(transport=transport, formula_ids=formula_ids)
    return path, transport


def _fill_event(order_intent_id: str, *, qty: int, price: float, status: str = "FILLED") -> BrokerExecutionEvent:
    return BrokerExecutionEvent(
        broker_event_id=f"BE-{order_intent_id}",
        order_intent_id=order_intent_id,
        broker_status=status,
        event_time="2026-08-17T09:15:02+00:00",
        filled_quantity=qty,
        fill_price=price,
    )


# --- 15.1 Order Intent ---


def test_order_intent_carries_required_canonical_fields():
    auth, sizing = _sizing()
    instrument = _instrument()
    factory = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
        order_type="LIMIT",
        limit_price=152.5,
        causal_parent_ids=("DEC-1", "OPP-1"),
    )

    intent = factory.create(instrument)

    assert intent.order_intent_id
    assert intent.idempotency_key
    assert intent.instrument_id == "NIFTY26AUG24500CE"
    assert intent.side == "BUY"
    assert intent.quantity == sizing.final_quantity
    assert intent.quantity > 0
    assert intent.order_type == "LIMIT"
    assert intent.limit_price == 152.5
    assert intent.created_at == CREATED_AT
    assert intent.authorization_id == "AUTH-1"
    assert instrument.selection_id in intent.causal_parent_ids
    assert intent.authorization_id in intent.causal_parent_ids
    assert "DEC-1" in intent.causal_parent_ids
    assert "OPP-1" in intent.causal_parent_ids
    intent.validate()


def test_order_quantity_comes_from_f108_not_a_hardcoded_constant():
    _, sizing_small = _sizing(authorized_risk=500.0, max_qty=25.0)
    _, sizing_large = _sizing(authorized_risk=5000.0, max_qty=200.0)
    assert sizing_small.final_quantity != sizing_large.final_quantity

    small = CanonicalOrderIntentFactory(
        authorization=_sizing(authorized_risk=500.0, max_qty=25.0)[0],
        sizing=sizing_small,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    large = CanonicalOrderIntentFactory(
        authorization=_sizing(authorized_risk=5000.0, max_qty=200.0)[0],
        sizing=sizing_large,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())

    assert small.quantity == sizing_small.final_quantity
    assert large.quantity == sizing_large.final_quantity
    assert small.quantity < large.quantity


def test_order_factory_rejects_authorization_identity_mismatch():
    auth, sizing = _sizing(opportunity_id="AUTH-1")
    factory = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    )
    with pytest.raises(OrderIntentError, match="authorization identity"):
        factory.create(_instrument(auth_id="AUTH-OTHER"))


def test_order_factory_rejects_unauthorized_risk_state():
    auth, sizing = _sizing()
    unauthorized = RiskAuthorization(
        opportunity_id=auth.opportunity_id,
        authorized_risk=auth.authorized_risk,
        risk_state=RiskState.UNAUTHORIZED,
        policy_version=auth.policy_version,
        issued_at=auth.issued_at,
    )
    with pytest.raises(OrderIntentError, match="unauthorized"):
        CanonicalOrderIntentFactory(
            authorization=unauthorized,
            sizing=sizing,
            side="BUY",
            created_at=CREATED_AT,
        )


def test_order_factory_rejects_invalid_or_zero_sizing():
    auth, _ = _sizing()
    invalid = PositionSizingAssessment(
        target_quantity_unconstrained=0,
        target_quantity_constrained=0,
        final_quantity=0,
        gross_authorized_risk=0.0,
        effective_authorized_risk=0.0,
        authorized_risk_budget=5000.0,
        valid=False,
        reason="zero_authorized_quantity",
    )
    with pytest.raises(OrderIntentError, match="sizing"):
        CanonicalOrderIntentFactory(
            authorization=auth,
            sizing=invalid,
            side="BUY",
            created_at=CREATED_AT,
        )


def test_order_factory_is_deterministic_under_replay_context():
    auth, sizing = _sizing()
    instrument = _instrument()
    ctx = ReplayContext(
        decision_time=CREATED_AT,
        event_time=CREATED_AT,
        sequence_seed=7,
    )
    a = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
        replay_context=ctx,
    ).create(instrument)
    b = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
        replay_context=ctx,
    ).create(instrument)
    assert a == b
    assert a.order_intent_id == b.order_intent_id
    assert a.idempotency_key == b.idempotency_key
    assert a.fingerprint() == b.fingerprint()


# --- 15.2 / 15.3 Gateway ---


def test_production_gateway_blocks_and_submits_zero_orders():
    auth, sizing = _sizing()
    path, transport = _path(formula_ids=None)
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())

    with pytest.raises(ExecutionBlockedError):
        path.submit(intent)

    assert transport.submissions == []


def test_authorized_simulation_submits_once_and_is_idempotent():
    auth, sizing = _sizing()
    path, transport = _path(formula_ids=("F-004",))
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())

    first = path.submit(intent)
    second = path.submit(intent)

    assert first == second
    assert len(transport.submissions) == 1


# --- 15.4 Broker event mapping ---


def test_default_broker_map_covers_required_statuses():
    required = {"SUBMITTED", "PARTIALLY_FILLED", "FILLED", "REJECTED", "CANCELLED"}
    assert required.issubset(set(DEFAULT_BROKER_STATUS_MAP))
    assert DEFAULT_BROKER_STATUS_MAP["SUBMITTED"] is CanonicalExecutionStatus.SUBMITTED
    assert DEFAULT_BROKER_STATUS_MAP["PARTIALLY_FILLED"] is CanonicalExecutionStatus.PARTIALLY_FILLED
    assert DEFAULT_BROKER_STATUS_MAP["FILLED"] is CanonicalExecutionStatus.FILLED
    assert DEFAULT_BROKER_STATUS_MAP["REJECTED"] is CanonicalExecutionStatus.REJECTED
    assert DEFAULT_BROKER_STATUS_MAP["CANCELLED"] is CanonicalExecutionStatus.CANCELLED


@pytest.mark.parametrize(
    "broker_status, expected",
    [
        ("SUBMITTED", CanonicalExecutionStatus.SUBMITTED),
        ("PARTIALLY_FILLED", CanonicalExecutionStatus.PARTIALLY_FILLED),
        ("FILLED", CanonicalExecutionStatus.FILLED),
        ("REJECTED", CanonicalExecutionStatus.REJECTED),
        ("CANCELLED", CanonicalExecutionStatus.CANCELLED),
    ],
)
def test_gateway_maps_required_broker_statuses(broker_status, expected):
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)

    qty = sizing.final_quantity if broker_status in {"PARTIALLY_FILLED", "FILLED"} else 0
    price = 150.0 if qty else None
    event = path.receive(
        BrokerExecutionEvent(
            broker_event_id=f"BE-{broker_status}",
            order_intent_id=intent.order_intent_id,
            broker_status=broker_status,
            event_time="2026-08-17T09:15:02+00:00",
            filled_quantity=qty,
            fill_price=price,
        )
    )
    assert event.event_type is expected
    assert event.order_intent_id == intent.order_intent_id


def test_unknown_broker_status_fails_closed_to_unknown():
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)
    event = path.receive(
        BrokerExecutionEvent(
            broker_event_id="BE-WEIRD",
            order_intent_id=intent.order_intent_id,
            broker_status="PROVIDER_WEIRD_CODE",
            event_time="2026-08-17T09:15:02+00:00",
        )
    )
    assert event.event_type is CanonicalExecutionStatus.UNKNOWN


# --- 16 Position projection ---


def test_fill_projects_position_from_execution_event():
    auth, sizing = _sizing()
    instrument = _instrument()
    path, _ = _path()
    result = path.submit_and_project(
        instrument=instrument,
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
        broker_event=_fill_event("pending", qty=sizing.final_quantity, price=150.0),
        risk_boundary=90.0,
    )

    assert result.execution.event_type is CanonicalExecutionStatus.FILLED
    assert result.position.quantity == sizing.final_quantity
    assert result.position.average_price == 150.0
    assert result.position.instrument_id == instrument.instrument_id
    assert result.position.direction == "BUY"
    assert result.position.lifecycle_state == "OPEN"
    assert result.position.open_time == "2026-08-17T09:15:02+00:00"
    assert result.position.risk_boundary == 90.0
    assert result.position.source_execution_event_id == result.execution.execution_event_id


def test_duplicate_execution_event_is_idempotent():
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)
    fill = _fill_event(intent.order_intent_id, qty=sizing.final_quantity, price=150.0)

    first = path.receive_and_project(fill, instrument_id="NIFTY26AUG24500CE", side="BUY")
    second = path.receive_and_project(fill, instrument_id="NIFTY26AUG24500CE", side="BUY")

    assert first.position.quantity == second.position.quantity == sizing.final_quantity
    assert first.position.average_price == second.position.average_price == 150.0


def test_fill_after_cancel_fails_closed():
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)
    path.receive_and_project(
        BrokerExecutionEvent(
            broker_event_id="BE-CANCEL",
            order_intent_id=intent.order_intent_id,
            broker_status="CANCELLED",
            event_time="2026-08-17T09:15:02+00:00",
        ),
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
    )
    with pytest.raises(PositionInvariantError, match="cancel"):
        path.receive_and_project(
            BrokerExecutionEvent(
                broker_event_id="BE-LATE-FILL",
                order_intent_id=intent.order_intent_id,
                broker_status="FILLED",
                event_time="2026-08-17T09:15:03+00:00",
                filled_quantity=sizing.final_quantity,
                fill_price=150.0,
            ),
            instrument_id="NIFTY26AUG24500CE",
            side="BUY",
        )


def test_reversal_that_would_flip_sign_fails_closed():
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)
    path.receive_and_project(
        _fill_event(intent.order_intent_id, qty=sizing.final_quantity, price=150.0),
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
        order_side_map={intent.order_intent_id: "BUY"},
    )
    with pytest.raises(PositionInvariantError, match="exceeds"):
        path.receive_and_project(
            BrokerExecutionEvent(
                broker_event_id="BE-REVERSAL",
                order_intent_id="oi-exit-reversal",
                broker_status="FILLED",
                event_time="2026-08-17T09:15:04+00:00",
                filled_quantity=sizing.final_quantity + 25,
                fill_price=160.0,
            ),
            instrument_id="NIFTY26AUG24500CE",
            side="BUY",
            order_side_map={
                intent.order_intent_id: "BUY",
                "oi-exit-reversal": "SELL",
            },
        )


def test_zero_and_negative_fill_quantity_fail_closed():
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)

    with pytest.raises(ValueError):
        path.receive(
            BrokerExecutionEvent(
                broker_event_id="BE-ZERO",
                order_intent_id=intent.order_intent_id,
                broker_status="FILLED",
                event_time="2026-08-17T09:15:02+00:00",
                filled_quantity=0,
                fill_price=150.0,
            )
        )
    with pytest.raises(ValueError):
        path.receive(
            BrokerExecutionEvent(
                broker_event_id="BE-NEG",
                order_intent_id=intent.order_intent_id,
                broker_status="FILLED",
                event_time="2026-08-17T09:15:02+00:00",
                filled_quantity=-25,
                fill_price=150.0,
            )
        )


def test_out_of_order_execution_event_fails_closed():
    auth, sizing = _sizing()
    path, _ = _path()
    intent = CanonicalOrderIntentFactory(
        authorization=auth,
        sizing=sizing,
        side="BUY",
        created_at=CREATED_AT,
    ).create(_instrument())
    path.submit(intent)
    path.receive_and_project(
        BrokerExecutionEvent(
            broker_event_id="BE-LATE",
            order_intent_id=intent.order_intent_id,
            broker_status="PARTIALLY_FILLED",
            event_time="2026-08-17T09:15:10+00:00",
            filled_quantity=25,
            fill_price=150.0,
        ),
        instrument_id="NIFTY26AUG24500CE",
        side="BUY",
    )
    with pytest.raises(PositionInvariantError, match="out-of-order"):
        path.receive_and_project(
            BrokerExecutionEvent(
                broker_event_id="BE-EARLY",
                order_intent_id=intent.order_intent_id,
                broker_status="PARTIALLY_FILLED",
                event_time="2026-08-17T09:15:02+00:00",
                filled_quantity=25,
                fill_price=149.0,
            ),
            instrument_id="NIFTY26AUG24500CE",
            side="BUY",
        )


def test_full_path_replay_is_deterministic():
    auth, sizing = _sizing()
    instrument = _instrument()
    ctx = ReplayContext(decision_time=CREATED_AT, event_time=CREATED_AT, sequence_seed=3)

    def run_once():
        path, transport = _path()
        result = path.submit_and_project(
            instrument=instrument,
            authorization=auth,
            sizing=sizing,
            side="BUY",
            created_at=CREATED_AT,
            replay_context=ctx,
            broker_event=_fill_event("pending", qty=sizing.final_quantity, price=150.0),
            risk_boundary=90.0,
        )
        return result, transport

    a, ta = run_once()
    b, tb = run_once()
    assert a.order == b.order
    assert a.execution.event_type == b.execution.event_type
    assert a.position.quantity == b.position.quantity
    assert a.position.average_price == b.position.average_price
    assert a.position.direction == b.position.direction
    assert len(ta.submissions) == len(tb.submissions) == 1
