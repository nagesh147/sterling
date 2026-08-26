from __future__ import annotations

from types import SimpleNamespace

from app.engines.adaptive_edge.f107_f110_pipeline import F107F110Decision
from app.engines.adaptive_edge.f110_order_admission import create_admitted_order


def test_f110_blocks_order_intent_when_upstream_not_admitted():
    result = create_admitted_order(
        F107F110Decision(False, None, None, None, "risk_sizing_ineligible"),
        selection_id="sel-1", side="BUY", intent_version="v1", created_at="2026-08-19T03:45:00Z",
    )
    assert result.admitted is False
    assert result.order_intent is None


def test_f110_creates_intent_only_from_positive_sizing():
    decision = F107F110Decision(
        True, SimpleNamespace(valid=True), SimpleNamespace(valid=True, final_quantity=25), "NIFTY-CE", "admitted"
    )
    result = create_admitted_order(
        decision,
        selection_id="sel-1", side="BUY", intent_version="v1", created_at="2026-08-19T03:45:00Z",
    )
    assert result.admitted is True
    assert result.order_intent.quantity == 25
    assert result.order_intent.instrument_id == "NIFTY-CE"


def test_f110_rejects_zero_quantity():
    decision = F107F110Decision(
        True, SimpleNamespace(valid=True), SimpleNamespace(valid=True, final_quantity=0), "NIFTY-CE", "admitted"
    )
    result = create_admitted_order(
        decision,
        selection_id="sel-1", side="BUY", intent_version="v1", created_at="2026-08-19T03:45:00Z",
    )
    assert result.admitted is False
    assert result.order_intent is None
