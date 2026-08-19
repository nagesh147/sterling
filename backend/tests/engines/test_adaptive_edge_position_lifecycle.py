"""Integration: projected PositionState → F-112/A177 protection → A126/F-111 lifecycle.

Composition only. F-111 and F-112 remain LOCKED. No re-entry score is invented.
"""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.broker_event_mapper import BrokerExecutionEvent
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.e2e import SelectedInstrument
from app.engines.adaptive_edge.execution_gate import ExecutionBlockedError
from app.engines.adaptive_edge.execution_path import AdaptiveEdgeExecutionPath
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.lifecycle_engine import LifecycleAction
from app.engines.adaptive_edge.position_lifecycle import (
    ManagedPosition,
    PostExitError,
)
from app.engines.adaptive_edge.protection import ProtectionPolicy
from app.engines.adaptive_edge.risk_sizing import (
    ExecutionCostParameters,
    ParameterEstimationMethod,
    ParameterMetadata,
    ParameterValidationStatus,
    SizingParameters,
    calculate_position_sizing,
    calculate_risk_per_unit,
)


CREATED_AT = "2026-08-17T03:45:00+00:00"  # 09:15 IST
ENTRY_PRICE = 150.0
STOP_POINTS = 10.0


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


def _open_position(*, formula_ids: tuple[str, ...] | None = ("F-004",)):
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
        authorized_risk=5000.0,
        risk_state=RiskState.AUTHORIZED,
        policy_version="risk-v1",
        issued_at=CREATED_AT,
    )
    sizing = calculate_position_sizing(
        auth,
        risk_unit,
        SizingParameters(
            max_position_qty=_param("max_position_qty", 100.0, "contracts"),
            max_capital_allocation=_param("max_capital_allocation", 100_000.0, "INR"),
            lot_size=_param("lot_size", 25.0, "contracts"),
        ),
    )
    instrument = SelectedInstrument(
        selection_id="SEL-AUTH-1",
        intent_id="AUTH-1",
        instrument_id="NIFTY26AUG24500CE",
        selection_version="f109-research-v1",
        selected_at=CREATED_AT,
    )
    transport = RecordingTransport()
    path = AdaptiveEdgeExecutionPath(transport=transport, formula_ids=formula_ids)
    executed = path.submit_and_project(
        instrument=instrument,
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
            fill_price=ENTRY_PRICE,
        ),
        risk_boundary=ENTRY_PRICE - STOP_POINTS,
    )
    managed = ManagedPosition.from_execution(
        executed,
        policy=ProtectionPolicy(
            "RESEARCH_NOT_LIVE",
            protective_stop_points=STOP_POINTS,
            trail_points=5.0,
            profit_lock_activation_points=20.0,
            profit_lock_offset_points=5.0,
        ),
    )
    return managed, path, transport, executed, auth


def test_projected_position_holds_before_any_protection_event():
    managed, _, _, executed, _ = _open_position()
    assert executed.position.lifecycle_state == "OPEN"
    assert executed.position.quantity > 0

    tick = managed.on_mark(ENTRY_PRICE + 2.0, "2026-08-17T04:00:00+00:00")
    assert tick.exit_required is False
    assert tick.lifecycle.action == LifecycleAction.HOLD.value
    assert tick.lifecycle.position_id == executed.position.position_id
    assert tick.protection.hit is False
    assert tick.position.quantity == executed.position.quantity


def test_protective_stop_on_projected_position_exits():
    managed, _, _, _, _ = _open_position()
    tick = managed.on_mark(ENTRY_PRICE - STOP_POINTS, "2026-08-17T04:01:00+00:00")
    assert tick.protection.authority == "PROTECTIVE_STOP"
    assert tick.exit_required is True
    assert tick.lifecycle.action == LifecycleAction.EXIT_HARD_STOP.value
    assert tick.lifecycle.lifecycle_state == "FLAT"
    assert managed.outcome_finalized is True


def test_profit_lock_then_giveback_exits_on_projected_position():
    managed, _, _, _, _ = _open_position()
    armed = managed.on_mark(ENTRY_PRICE + 20.0, "2026-08-17T04:02:00+00:00")
    assert armed.protection.lock_active is True
    assert armed.exit_required is False
    fire = managed.on_mark(ENTRY_PRICE + 15.0, "2026-08-17T04:03:00+00:00")
    assert fire.protection.authority == "PROFIT_LOCK"
    assert fire.lifecycle.action == LifecycleAction.EXIT_PROFIT_PROTECTION.value
    assert fire.exit_required is True


def test_trailing_stop_tightens_and_never_loosens():
    managed, _, _, _, _ = _open_position()
    up = managed.on_mark(ENTRY_PRICE + 10.0, "2026-08-17T04:04:00+00:00")
    assert up.protection.trail_price == ENTRY_PRICE + 5.0
    pullback = managed.on_mark(ENTRY_PRICE + 8.0, "2026-08-17T04:05:00+00:00")
    assert pullback.protection.trail_price == ENTRY_PRICE + 5.0
    assert pullback.protection.extreme == ENTRY_PRICE + 10.0
    hit = managed.on_mark(ENTRY_PRICE + 5.0, "2026-08-17T04:06:00+00:00")
    assert hit.protection.authority == "TRAILING_PROTECTION"
    assert hit.lifecycle.action == LifecycleAction.EXIT_PROFIT_PROTECTION.value


def test_session_cutoff_1445_ist_flattens_projected_position():
    managed, _, _, _, _ = _open_position()
    before = managed.on_mark(ENTRY_PRICE + 1.0, "2026-08-17T09:14:00+00:00")  # 14:44 IST
    assert before.exit_required is False
    cutoff = managed.on_mark(ENTRY_PRICE + 1.0, "2026-08-17T09:15:00+00:00")  # 14:45 IST
    assert cutoff.exit_required is True
    assert cutoff.lifecycle.action == LifecycleAction.EXIT_SESSION_CUTOFF.value


def test_risk_boundary_on_position_state_is_hard_risk():
    managed, _, _, executed, _ = _open_position()
    assert executed.position.risk_boundary == ENTRY_PRICE - STOP_POINTS
    tick = managed.on_mark(executed.position.risk_boundary, "2026-08-17T04:07:00+00:00")
    assert tick.exit_required is True
    assert tick.lifecycle.action == LifecycleAction.EXIT_HARD_STOP.value


def test_explicit_continuation_failure_exits_without_inventing_a_score():
    managed, _, _, _, _ = _open_position()
    tick = managed.on_mark(
        ENTRY_PRICE + 1.0,
        "2026-08-17T04:08:00+00:00",
        economic_edge_valid=False,
    )
    assert tick.lifecycle.action == LifecycleAction.EXIT_ECONOMIC_COLLAPSE.value
    assert tick.exit_required is True


def test_flatten_after_exit_projects_zero_quantity():
    managed, path, transport, executed, _ = _open_position()
    managed.on_mark(ENTRY_PRICE - STOP_POINTS, "2026-08-17T04:09:00+00:00")
    closed = managed.flatten(
        path,
        fill_price=ENTRY_PRICE - STOP_POINTS,
        event_time="2026-08-17T04:09:01+00:00",
    )
    assert closed.position.quantity == 0
    assert closed.position.lifecycle_state == "FLAT"
    assert len(transport.submissions) == 2
    assert transport.submissions[-1].side == "SELL"
    assert transport.submissions[-1].quantity == executed.position.quantity


def test_post_exit_blocks_reuse_of_the_same_authorization():
    managed, path, _, _, auth = _open_position()
    managed.on_mark(ENTRY_PRICE - STOP_POINTS, "2026-08-17T04:10:00+00:00")
    managed.flatten(path, fill_price=140.0, event_time="2026-08-17T04:10:01+00:00")
    later = managed.on_mark(ENTRY_PRICE + 3.0, "2026-08-17T04:20:00+00:00")
    assert later.exit_required is False
    assert later.lifecycle.action == "NO_ACTION"
    assert later.lifecycle.reason == "outcome_finalized"
    with pytest.raises(PostExitError, match="authorization cannot be reused"):
        managed.assert_independent_opportunity(auth.opportunity_id)


def test_flatten_without_exit_decision_fails_closed():
    managed, path, _, _, _ = _open_position()
    with pytest.raises(PostExitError, match="outcome not finalized"):
        managed.flatten(path, fill_price=ENTRY_PRICE, event_time="2026-08-17T04:11:00+00:00")


def test_formulas_stay_locked_and_production_stays_blocked():
    assert FORMULAS["F-111"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-112"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-113"].status is FormulaStatus.LOCKED
    with pytest.raises(ExecutionBlockedError):
        _open_position(formula_ids=None)
