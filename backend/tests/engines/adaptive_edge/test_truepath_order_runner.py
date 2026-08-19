from __future__ import annotations

from app.engines.adaptive_edge.event_boundary import CanonicalEventBoundary
from app.engines.adaptive_edge.f101_f106_contracts import F106OptionCandidate
from app.engines.adaptive_edge.f101_f106_pipeline import F101F106PipelineInput
from app.engines.adaptive_edge.f107_f110_pipeline import F107F110Input
from app.engines.adaptive_edge.contracts import RiskAuthorization, RiskState
from app.engines.adaptive_edge.risk_sizing import ExecutionCostParameters, SizingParameters
from app.engines.adaptive_edge.truepath_order_runner import build_order_from_canonical_event


def _event():
    return CanonicalEventBoundary.create(
        record_id="TD-BAR-NIFTY-1", event_type="bar", instrument_id="NIFTY",
        event_time="2026-08-19T03:45:00+00:00", available_at="2026-08-19T03:46:00+00:00",
        source="truedata", source_version="2.6",
        payload={"open":100,"high":105,"low":99,"close":104,"volume":1000,"oi":100},
        source_timestamp="2026-08-19T03:45:00+00:00",
    )


def _upstream():
    return F101F106PipelineInput(
        feature_values={"vwap":104.0,"poc":103.0}, quality_ok=True,
        observation_cutoff="2026-08-19T03:45:00+00:00", decision_time="2026-08-19T03:46:00+00:00",
        probabilities=(0.7,0.2,0.1), directional_edge=0.2,
        eligibility_reason="directional_edge", expected_gross_value=20.0,
        execution_cost=2.0, conservative_net_value=18.0, minimum_net_value=5.0,
        horizons={"MICRO":1.0}, selected_horizon="MICRO",
        option_candidates=(F106OptionCandidate("NIFTY-CE",18.0,True,True,True,True),),
    )


def _risk():
    return F107F110Input(
        entry_price=100.0, initial_stop=95.0,
        risk_authorization=RiskAuthorization("opp-1",500.0,RiskState.AUTHORIZED,"policy-v1","2026-08-19T03:46:00+00:00"),
        candidate=F106OptionCandidate("NIFTY-CE",18.0,True,True,True,True),
        costs=ExecutionCostParameters(fixed_cost=1.0, variable_cost_rate=0.001),
        sizing=SizingParameters(lot_size=25, max_lots=4, max_capital=10000.0),
    )


def test_truepath_reaches_order_with_f110_proof():
    result = build_order_from_canonical_event(_event(), upstream=_upstream(), risk_entry=_risk(),
        selection_id="sel-1", side="BUY", intent_version="v1", created_at="2026-08-19T03:46:00+00:00")
    assert result.order_ready is True
    assert result.admission.order_intent is not None
    assert result.f110_proof


def test_truepath_stops_before_risk_when_economics_fail():
    data = _upstream()
    bad = F101F106PipelineInput(**{**data.__dict__, "expected_gross_value": None, "conservative_net_value": None})
    result = build_order_from_canonical_event(_event(), upstream=bad, risk_entry=_risk(),
        selection_id="sel-1", side="BUY", intent_version="v1", created_at="2026-08-19T03:46:00+00:00")
    assert result.order_ready is False
    assert result.risk_entry is None


def test_truepath_rejects_lookahead_event():
    event = CanonicalEventBoundary.create(
        record_id="bad", event_type="bar", instrument_id="NIFTY",
        event_time="2026-08-19T03:46:00+00:00", available_at="2026-08-19T03:45:00+00:00",
        source="truedata", source_version="2.6", payload={"close":1},
    )
    try:
        build_order_from_canonical_event(event, upstream=_upstream(), risk_entry=_risk(),
            selection_id="sel-1", side="BUY", intent_version="v1", created_at="2026-08-19T03:46:00+00:00")
    except ValueError:
        return
    raise AssertionError("lookahead event must be rejected")
