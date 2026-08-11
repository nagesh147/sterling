"""Master-Spec Adaptive Edge adapter.

Direction and probability come from a versioned probability model. Economic
eligibility is evaluated separately; this adapter never converts an arbitrary
feature-weighted score into a trade decision.
"""
from __future__ import annotations

from dataclasses import dataclass

from .economic_engine import EconomicEvaluation
from .probability_engine import ModelParameters, Prediction, predict


@dataclass(frozen=True)
class DirectionalPrediction:
    prediction: Prediction
    p_up: float
    p_down: float
    p_neutral: float

    @property
    def direction(self) -> int:
        if self.p_up > self.p_down and self.p_up > self.p_neutral:
            return 1
        if self.p_down > self.p_up and self.p_down > self.p_neutral:
            return -1
        return 0

    @property
    def directional_probability(self) -> float:
        return max(self.p_up, self.p_down)


def evaluate_direction(
    *,
    prediction_id: str,
    opportunity_id: str,
    prediction_time: str,
    feature_snapshot_id: str,
    features: tuple[float, ...],
    parameters: ModelParameters,
) -> DirectionalPrediction:
    prediction = predict(
        prediction_id=prediction_id,
        opportunity_id=opportunity_id,
        prediction_time=prediction_time,
        feature_snapshot_id=feature_snapshot_id,
        features=features,
        parameters=parameters,
    )
    try:
        p_up = prediction.outputs["up"]
        p_down = prediction.outputs["down"]
        p_neutral = prediction.outputs["neutral"]
    except KeyError as exc:
        raise ValueError("model must expose up, down, and neutral classes") from exc
    return DirectionalPrediction(prediction, p_up, p_down, p_neutral)


def eligible_from_economics(evaluation: EconomicEvaluation) -> bool:
    return evaluation.conservative_net_value > 0.0
