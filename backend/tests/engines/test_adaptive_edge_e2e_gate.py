from app.engines.adaptive_edge.e2e import PredictionEvidence, run_e2e
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.feature_engine import (
    FeatureInput,
    InstrumentContext,
    build_feature_snapshot,
)


class FakeFeatureBuilder:
    def build(self, event):
        return build_feature_snapshot(
            snapshot_id="snap-1",
            strategy_version="strategy-1",
            feature_set_version="features-1",
            observation_cutoff_time=event.event_time,
            decision_time=event.available_at,
            instrument_context=InstrumentContext(event.instrument_id),
            inputs=[FeatureInput("x", 1.0, event.event_time)],
        )


class FakePredictionEngine:
    def predict(self, snapshot):
        return PredictionEvidence(
            prediction_id="pred-1",
            snapshot_id=snapshot.snapshot_id,
            opportunity_id="opp-1",
            strategy_version=snapshot.strategy_version,
            model_version="model-1",
            prediction_time=snapshot.decision_time,
            target_definition_version="target-1",
            horizon_definition_version="horizon-1",
            prediction_type="direction",
            prediction_value=1.0,
            uncertainty=0.1,
            calibration_reference=None,
            provenance={"source": "test"},
        )


class FailingExecutionGateway:
    # e2e reads this to check the gateway's authorization scope matches the
    # run's formula scope. None means "no scope configured", which is what a
    # double that must never be reached should say.
    authorized_formula_ids = None

    def submit(self, order):
        raise AssertionError("execution must not be reached while the gate is blocked")

    def receive(self, event):
        raise AssertionError("broker execution must not be reached while the gate is blocked")


def _event():
    return CanonicalMarketEvent(
        record_id="evt-1",
        event_type="QUOTE",
        instrument_id="NIFTY-I",
        event_time="2026-08-17T09:30:00+05:30",
        available_at="2026-08-17T09:30:00+05:30",
        source="test",
        source_version="1",
        payload={"ltp": 25000.0},
        source_timestamp="2026-08-17T09:30:00+05:30",
        receipt_timestamp="2026-08-17T09:30:00.100000+05:30",
        sequence=1,
        provenance={"provider": "test"},
    )


def test_e2e_fails_closed_before_locked_strategy_math_or_execution():
    trace = run_e2e(
        _event(),
        feature_builder=FakeFeatureBuilder(),
        prediction_engine=FakePredictionEngine(),
        edge_formula=None,
        decision_engine=None,
        risk_authorizer=None,
        instrument_selector=None,
        order_factory=None,
        execution_gateway=FailingExecutionGateway(),
        position_projector=None,
        lifecycle_engine=None,
        execution_cost=10.0,
    )

    assert trace.execution_gate.authorized is False
    assert trace.execution_gate.blocking_formulas == tuple(
        f"F-{number:03d}" for number in range(101, 115)
    )
    assert trace.prediction is not None
    assert trace.edge is None
    assert trace.economics is None
    assert trace.decision is None
    assert trace.authorization is None
    assert trace.instrument is None
    assert trace.order is None
    assert trace.execution is None
    assert trace.position is None
    assert trace.lifecycle is None
    assert [record.stage for record in trace.audit] == [
        "market_event",
        "feature_snapshot",
        "prediction",
    ]
