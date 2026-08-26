"""Adapter exposing the reconstructed F-102 model through EdgeFormula."""
from __future__ import annotations

from .edge import EdgeAssessment
from .feature_engine import FeatureSnapshot
from .formula_registry import get_formula
from .model import MarketFeatures, f101_feature_score, f102_edge_score


class ReconstructedEdgeFormula:
    formula_id = "F-102"
    formula_version = "0.1.0"

    def evaluate(self, snapshot: FeatureSnapshot) -> EdgeAssessment:
        required = (
            "trend",
            "momentum",
            "relative_volume",
            "volatility_expansion",
            "expected_move",
            "confidence",
        )
        missing = [name for name in required if name not in snapshot.values]
        if missing:
            raise ValueError(f"missing Adaptive Edge inputs: {', '.join(missing)}")

        features = MarketFeatures(
            trend=snapshot.values["trend"],
            momentum=snapshot.values["momentum"],
            relative_volume=snapshot.values["relative_volume"],
            volatility_expansion=snapshot.values["volatility_expansion"],
            expected_move=max(snapshot.values["expected_move"], 0.0),
            confidence=snapshot.values["confidence"],
        )
        feature_score = f101_feature_score(features)
        edge_score = f102_edge_score(feature_score)
        gross = abs(edge_score) * features.expected_move
        definition = get_formula(self.formula_id)
        return EdgeAssessment(
            opportunity_id=f"adaptive-edge:{snapshot.observation_time}",
            score=edge_score,
            confidence=features.confidence,
            expected_gross_value=gross,
            formula_id=definition.formula_id,
            formula_version=definition.version,
            inputs={
                "feature_score": feature_score,
                "expected_move": features.expected_move,
                "confidence": features.confidence,
            },
        )
