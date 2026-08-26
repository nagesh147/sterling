"""Deterministic multinomial-logistic research fitter.

This implements the model family already present in canonical_math.py. All
optimization choices remain explicit research configuration and are not treated
as strategy truth. Training data must already have been causally partitioned by
the walk-forward research boundary before this function is called.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, isfinite
from typing import Sequence

from .probability_engine import ModelParameters


class ParameterFittingError(ValueError):
    pass


@dataclass(frozen=True)
class FittingConfig:
    learning_rate: float = 0.05
    epochs: int = 500
    l2_regularization: float = 0.01
    tolerance: float = 1e-10

    def __post_init__(self) -> None:
        if self.learning_rate <= 0 or self.epochs <= 0 or self.l2_regularization < 0 or self.tolerance < 0:
            raise ParameterFittingError("invalid fitting configuration")


@dataclass(frozen=True)
class FittingResult:
    parameters: ModelParameters
    initial_loss: float
    final_loss: float
    epochs_run: int


def _validate_rows(features: Sequence[Sequence[float]], labels: Sequence[int], class_count: int) -> int:
    if not features or len(features) != len(labels):
        raise ParameterFittingError("features and labels must be non-empty and aligned")
    width = len(features[0])
    if width == 0 or any(len(row) != width for row in features):
        raise ParameterFittingError("feature rows must have equal non-zero width")
    if any(not all(isfinite(value) for value in row) for row in features):
        raise ParameterFittingError("features must be finite")
    if class_count < 2 or any(label < 0 or label >= class_count for label in labels):
        raise ParameterFittingError("labels must be valid class indices")
    return width


def _softmax(logits: Sequence[float]) -> list[float]:
    pivot = max(logits)
    weights = [exp(value - pivot) for value in logits]
    total = sum(weights)
    return [weight / total for weight in weights]


def _loss(
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    coefficients: Sequence[Sequence[float]],
    intercepts: Sequence[float],
    regularization: float,
) -> float:
    total = 0.0
    for row, label in zip(features, labels):
        probabilities = _softmax(
            [sum(w * x for w, x in zip(weights, row)) + bias for weights, bias in zip(coefficients, intercepts)]
        )
        total -= __import__("math").log(max(probabilities[label], 1e-300))
    total /= len(features)
    penalty = regularization * sum(weight * weight for row in coefficients for weight in row)
    return total + penalty


def fit_multinomial_logistic(
    *,
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    class_names: Sequence[str],
    config: FittingConfig,
    model_version: str,
) -> FittingResult:
    """Fit coefficients using deterministic full-batch gradient descent.

    Intercepts are fitted but are excluded from the L2 penalty, matching the
    canonical loss definition ``CrossEntropy + lambda ||beta||^2``.
    """
    class_count = len(class_names)
    width = _validate_rows(features, labels, class_count)
    coefficients = [[0.0 for _ in range(width)] for _ in range(class_count)]
    intercepts = [0.0 for _ in range(class_count)]
    initial_loss = _loss(features, labels, coefficients, intercepts, config.l2_regularization)
    previous_loss = initial_loss

    for epoch in range(1, config.epochs + 1):
        coefficient_gradient = [[0.0 for _ in range(width)] for _ in range(class_count)]
        intercept_gradient = [0.0 for _ in range(class_count)]
        for row, label in zip(features, labels):
            probabilities = _softmax(
                [sum(w * x for w, x in zip(weights, row)) + bias for weights, bias in zip(coefficients, intercepts)]
            )
            for class_index, probability in enumerate(probabilities):
                error = probability - (1.0 if class_index == label else 0.0)
                intercept_gradient[class_index] += error
                for feature_index, value in enumerate(row):
                    coefficient_gradient[class_index][feature_index] += error * value

        count = float(len(features))
        for class_index in range(class_count):
            intercepts[class_index] -= config.learning_rate * intercept_gradient[class_index] / count
            for feature_index in range(width):
                gradient = coefficient_gradient[class_index][feature_index] / count
                gradient += 2.0 * config.l2_regularization * coefficients[class_index][feature_index]
                coefficients[class_index][feature_index] -= config.learning_rate * gradient

        current_loss = _loss(features, labels, coefficients, intercepts, config.l2_regularization)
        if abs(previous_loss - current_loss) <= config.tolerance:
            previous_loss = current_loss
            return FittingResult(
                ModelParameters(model_version, tuple(class_names), tuple(tuple(row) for row in coefficients), tuple(intercepts), config.l2_regularization),
                initial_loss,
                current_loss,
                epoch,
            )
        previous_loss = current_loss

    return FittingResult(
        ModelParameters(model_version, tuple(class_names), tuple(tuple(row) for row in coefficients), tuple(intercepts), config.l2_regularization),
        initial_loss,
        previous_loss,
        config.epochs,
    )
