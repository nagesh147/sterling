"""INV-ENTRY-003 / A177 / A126 admission. Not a re-entry score. Not F-114 portfolio math."""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.admission import (
    AdmissionError,
    evaluate_entry_admission,
    require_entry_admitted,
)
from app.engines.adaptive_edge.e2e import PositionState
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus


def _open(qty: int = 25) -> PositionState:
    return PositionState(
        position_id="pos-1",
        instrument_id="NIFTY26AUG24500CE",
        quantity=qty,
        average_price=150.0,
        lifecycle_state="OPEN" if qty else "FLAT",
        source_execution_event_id="ex-1",
    )


def test_flat_before_cutoff_with_new_authorization_is_admitted():
    decision = evaluate_entry_admission(
        open_position=_open(0),
        authorization_id="AUTH-2",
        opportunity_id="OPP-2",
        decision_time="2026-08-17T04:00:00+00:00",
        consumed_authorization_ids=frozenset({"AUTH-1"}),
        entered_opportunity_ids=frozenset({"OPP-1"}),
    )
    assert decision.admitted is True
    assert "INV-ENTRY-003" in decision.invariants


def test_open_position_blocks_pyramid():
    decision = evaluate_entry_admission(
        open_position=_open(25),
        authorization_id="AUTH-2",
        opportunity_id="OPP-2",
        decision_time="2026-08-17T04:00:00+00:00",
    )
    assert decision.admitted is False
    assert decision.reason == "INV-ENTRY-003_pyramid_blocked"


def test_same_opportunity_cannot_enter_twice():
    decision = evaluate_entry_admission(
        open_position=None,
        authorization_id="AUTH-2",
        opportunity_id="OPP-1",
        decision_time="2026-08-17T04:00:00+00:00",
        entered_opportunity_ids=frozenset({"OPP-1"}),
    )
    assert decision.admitted is False
    assert decision.reason == "INV-ENTRY-003_same_opportunity"


def test_consumed_authorization_cannot_be_reused():
    decision = evaluate_entry_admission(
        open_position=None,
        authorization_id="AUTH-1",
        opportunity_id="OPP-2",
        decision_time="2026-08-17T04:00:00+00:00",
        consumed_authorization_ids=frozenset({"AUTH-1"}),
    )
    assert decision.admitted is False
    assert decision.reason == "A177_authorization_reuse_blocked"


def test_session_cutoff_blocks_new_entry():
    decision = evaluate_entry_admission(
        open_position=None,
        authorization_id="AUTH-2",
        opportunity_id="OPP-2",
        decision_time="2026-08-17T09:15:00+00:00",  # 14:45 IST
    )
    assert decision.admitted is False
    assert decision.reason == "A126_session_cutoff_blocks_entry"


def test_require_entry_admitted_fails_closed():
    with pytest.raises(AdmissionError, match="pyramid"):
        require_entry_admitted(
            open_position=_open(25),
            authorization_id="AUTH-2",
            opportunity_id="OPP-2",
            decision_time="2026-08-17T04:00:00+00:00",
        )


def test_execution_path_blocks_second_entry_while_open():
    from app.engines.adaptive_edge.broker_event_mapper import BrokerExecutionEvent
    from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
    from app.engines.adaptive_edge.e2e import SelectedInstrument
    from app.engines.adaptive_edge.execution_path import AdaptiveEdgeExecutionPath
    from app.engines.adaptive_edge.risk_sizing import (
        ExecutionCostParameters,
        ParameterEstimationMethod,
        ParameterMetadata,
        ParameterValidationStatus,
        SizingParameters,
        calculate_position_sizing,
        calculate_risk_per_unit,
    )

    def param(name: str, value: float, units: str = "INR") -> ParameterMetadata:
        return ParameterMetadata(
            name=name,
            value=value,
            units=units,
            version="1.0.0",
            provenance="Master_Spec_v1.0_Sec31_Sec36",
            estimation_method=ParameterEstimationMethod.CANONICAL_SPEC,
            validation_status=ParameterValidationStatus.VALIDATED,
        )

    class Transport:
        def submit(self, intent):
            return f"B-{intent.order_intent_id}"

    costs = ExecutionCostParameters(
        spread_cost=param("spread_cost", 1.0),
        expected_slippage=param("expected_slippage", 0.5),
        brokerage_per_unit=param("brokerage_per_unit", 0.2),
        exchange_charges_per_unit=param("exchange_charges_per_unit", 0.1),
        taxes_per_unit=param("taxes_per_unit", 0.1),
        latency_cost_per_unit=param("latency_cost_per_unit", 0.1),
    )
    risk = calculate_risk_per_unit(100.0, 90.0, costs)
    auth1 = RiskAuthorization("AUTH-1", 5000.0, RiskState.AUTHORIZED, "v1", "2026-08-17T03:45:00+00:00")
    auth2 = RiskAuthorization("AUTH-2", 5000.0, RiskState.AUTHORIZED, "v1", "2026-08-17T03:46:00+00:00")
    sizing = calculate_position_sizing(
        auth1,
        risk,
        SizingParameters(
            max_position_qty=param("max_position_qty", 100.0, "contracts"),
            max_capital_allocation=param("max_capital_allocation", 100000.0, "INR"),
            lot_size=param("lot_size", 25.0, "contracts"),
        ),
    )
    path = AdaptiveEdgeExecutionPath(transport=Transport(), formula_ids=("F-004",))
    path.submit_and_project(
        instrument=SelectedInstrument("SEL-1", "AUTH-1", "NIFTY-CE", "v1", "2026-08-17T03:45:00+00:00"),
        authorization=auth1,
        sizing=sizing,
        side="BUY",
        created_at="2026-08-17T03:45:00+00:00",
        broker_event=BrokerExecutionEvent(
            "be1", "pending", "FILLED", "2026-08-17T03:45:02+00:00",
            filled_quantity=sizing.final_quantity, fill_price=150.0,
        ),
    )
    with pytest.raises(AdmissionError, match="pyramid"):
        path.submit_and_project(
            instrument=SelectedInstrument("SEL-2", "AUTH-2", "NIFTY-PE", "v1", "2026-08-17T03:46:00+00:00"),
            authorization=auth2,
            sizing=sizing,
            side="BUY",
            created_at="2026-08-17T03:46:00+00:00",
            broker_event=BrokerExecutionEvent(
                "be2", "pending", "FILLED", "2026-08-17T03:46:02+00:00",
                filled_quantity=sizing.final_quantity, fill_price=150.0,
            ),
        )


def test_does_not_unlock_f113_or_invent_portfolio_risk():
    assert FORMULAS["F-113"].status is FormulaStatus.LOCKED
    assert FORMULAS["F-114"].status is FormulaStatus.LOCKED
    import app.engines.adaptive_edge.admission as admission
    assert not hasattr(admission, "reentry_score")
    assert not hasattr(admission, "PortfolioRisk")
