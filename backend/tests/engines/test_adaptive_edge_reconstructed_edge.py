import pytest

from app.engines.adaptive_edge.edge import StrategyFormulaLockedError, evaluate_edge
from app.engines.adaptive_edge.feature_engine import FeatureInput, build_feature_snapshot
from app.engines.adaptive_edge.reconstructed_edge import ReconstructedEdgeFormula


def snapshot():
    return build_feature_snapshot(
        observation_time="2026-08-11T10:00:00",
        decision_time="2026-08-11T10:00:00",
        inputs=[
            FeatureInput("trend", 0.8, "2026-08-11T09:59:00"),
            FeatureInput("momentum", 0.7, "2026-08-11T09:59:00"),
            FeatureInput("relative_volume", 0.6, "2026-08-11T09:58:00"),
            FeatureInput("volatility_expansion", 0.4, "2026-08-11T09:58:00"),
            FeatureInput("expected_move", 100.0, "2026-08-11T10:00:00"),
            FeatureInput("confidence", 0.8, "2026-08-11T10:00:00"),
        ],
        formula_ids=("F-101", "F-102"),
    )


def test_reconstructed_edge_produces_versioned_assessment():
    result = evaluate_edge(snapshot(), ReconstructedEdgeFormula())
    assert result.formula_id == "F-102"
    assert result.formula_version == "0.1.0"
    assert result.score > 0
    assert result.expected_gross_value > 0


def test_future_feature_is_rejected():
    with pytest.raises(ValueError, match="lookahead"):
        build_feature_snapshot(
            observation_time="2026-08-11T10:00:00",
            decision_time="2026-08-11T10:00:00",
            inputs=[FeatureInput("trend", 0.8, "2026-08-11T10:01:00")],
        )
