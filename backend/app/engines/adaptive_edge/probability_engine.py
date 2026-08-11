"""Parameterized probability engine matching the Master Specification.

The engine implements the mathematical model family but intentionally does not
invent coefficients, regularization, calibration, or thresholds. Those values
are learned and frozen by the walk-forward research pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .canonical_math import multinomial_logistic


@dataclass(frozen=True)
class ModelParameters:
    version: str
    classes: tuple[str, ...]
    coefficients: tuple[tuple[float, ...], ...]
    intercepts: tuple[float, ...]
    regularization: float


@dataclass(frozen=True)
class Prediction:
    prediction_id: str
    opportunity_id: str
    prediction_time: str
    feature_snapshot_id: str
    model_version: str
    outputs: dict[str, float]
    uncertainty: dict[str, float]


def predict(
    *,
    prediction_id: str,
    opportunity_id: str,
    prediction_time: str,
    feature_snapshot_id: str,
    features: Sequence[float],
    parameters: ModelParameters,
) -> Prediction:
    if len(parameters.classes) != len(parameters.coefficients):
        raise ValueError("class/coefficient dimensions do not match")
    probabilities = multinomial_logistic(features, parameters.coefficients, parameters.intercepts)
    outputs = dict(zip(parameters.classes, probabilities))
    return Prediction(
        prediction_id=prediction_id,
        opportunity_id=opportunity_id,
        prediction_time=prediction_time,
        feature_snapshot_id=feature_snapshot_id,
        model_version=parameters.version,
        outputs=outputs,
        uncertainty={},
    )
