"""F-110 conjunction on real snapshot/prediction/edge/economics objects."""
from __future__ import annotations

from app.engines.adaptive_edge.e2e import PredictionEvidence
from app.engines.adaptive_edge.economic import EconomicAssessment
from app.engines.adaptive_edge.edge import EdgeAssessment
from app.engines.adaptive_edge.entry_decision import (
    EntryAction,
    EntryDecisionEvidence,
    evaluate_entry_decision,
)
from app.engines.adaptive_edge.feature_engine import (
    FeatureInput,
    FeatureStatus,
    InstrumentContext,
    build_feature_snapshot,
)
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus


def _snapshot(status: FeatureStatus = FeatureStatus.VALID):
    return build_feature_snapshot(
        snapshot_id="SNAP-1",
        strategy_version="v2.0",
        feature_set_version="fset-v1",
        observation_cutoff_time="2026-08-17T03:45:00+00:00",
        decision_time="2026-08-17T03:45:00+00:00",
        instrument_context=InstrumentContext("NIFTY-I"),
        inputs=[FeatureInput("close", 24500.0, "2026-08-17T03:45:00+00:00", status)],
    )


def _prediction(snapshot) -> PredictionEvidence:
    return PredictionEvidence(
        prediction_id="PRED-1",
        snapshot_id=snapshot.snapshot_id,
        opportunity_id="OPP-1",
        strategy_version="v2.0",
        model_version="m1",
        prediction_time=snapshot.decision_time,
        target_definition_version="t1",
        horizon_definition_version="h1",
        prediction_type="CLASSIFICATION",
        prediction_value=0.7,
        uncertainty=0.1,
        calibration_reference=None,
        provenance={"src": "test"},
    )


def _edge() -> EdgeAssessment:
    return EdgeAssessment("OPP-1", 0.8, 0.9, 120.0, "F-004", "1.0", {})


def _econ(*, net: float = 100.0, eligible: bool = True) -> EconomicAssessment:
    return EconomicAssessment(120.0, 20.0, net, eligible)


def _evidence(**overrides) -> EntryDecisionEvidence:
    values = dict(
        option_type="CE",
        conservative_ev=60.0,
        directional_edge_ok=True,
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    )
    values.update(overrides)
    return EntryDecisionEvidence(**values)


def test_all_gates_pass_emits_buy_ce():
    snap = _snapshot()
    decision = evaluate_entry_decision(snap, _prediction(snap), _edge(), _econ(), _evidence())
    assert decision.action is EntryAction.BUY_CE
    assert decision.eligible is True
    assert all(decision.gates.values())


def test_missing_conservative_ev_fails_closed_without_inventing_q():
    snap = _snapshot()
    decision = evaluate_entry_decision(
        snap, _prediction(snap), _edge(), _econ(), _evidence(conservative_ev=None)
    )
    assert decision.action is EntryAction.NO_TRADE
    assert decision.reason == "missing_conservative_ev"
    assert decision.gates["ConservativeEV"] is False


def test_negative_conservative_ev_is_no_trade_even_if_ev_positive():
    snap = _snapshot()
    decision = evaluate_entry_decision(
        snap, _prediction(snap), _edge(), _econ(net=80.0), _evidence(conservative_ev=-1.0)
    )
    assert decision.action is EntryAction.NO_TRADE
    assert "ConservativeEV" in decision.reason


def test_stale_data_blocks_entry():
    snap = _snapshot(FeatureStatus.STALE)
    decision = evaluate_entry_decision(snap, _prediction(snap), _edge(), _econ(), _evidence())
    assert decision.action is EntryAction.NO_TRADE
    assert decision.gates["DataOK"] is False


def test_buy_pe_when_option_type_is_pe():
    snap = _snapshot()
    decision = evaluate_entry_decision(
        snap, _prediction(snap), _edge(), _econ(), _evidence(option_type="PE")
    )
    assert decision.action is EntryAction.BUY_PE


def test_f110_stays_locked():
    assert FORMULAS["F-110"].status is FormulaStatus.LOCKED
