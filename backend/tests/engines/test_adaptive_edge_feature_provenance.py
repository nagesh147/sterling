from app.engines.adaptive_edge.feature_engine import FeatureInput, build_feature_snapshot


def test_feature_snapshot_carries_formula_ids():
    snapshot = build_feature_snapshot(
        observation_time="2026-08-11T10:00:00+00:00",
        inputs=[FeatureInput("x", 1.0, "2026-08-11T09:59:00+00:00")],
        decision_time="2026-08-11T10:00:00+00:00",
        formula_ids=("F-101",),
    )
    assert snapshot.formula_ids == ("F-101",)
