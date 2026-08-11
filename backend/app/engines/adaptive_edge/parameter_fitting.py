"""Leakage-safe fitting for the Master Specification probability model.

Only training rows are used to estimate coefficients. Validation/holdout rows
are never touched by the fitter. This is intentionally a small deterministic
multinomial logistic implementation so the research pipeline has no hidden
sklearn state or accidental data split behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Sequence

from .probability_engine import ModelParameters, predict
from .research_dataset import ResearchRow


@dataclass(frozen=True)
class FitConfig:
    version: str
    classes: tuple[str, ...] = ("DOWN", "FLAT", "UP")
    learning_rate: float = 0.05
    epochs: int = 250
    l2: float = 1e-3


@dataclass(frozen=True)
class FitResult:
    parameters: ModelParameters
    training_loss: float
    validation_loss: float | None
    validation_accuracy: float | None


def _softmax(logits: Sequence[float]) -> tuple[float, ...]:
    pivot = max(logits)
    weights = [exp(x - pivot) for x in logits]
    total = sum(weights)
    return tuple(x / total for x in weights)


def _label_index(label: int) -> int:
    return { -1: 0, 0: 1, 1: 2 }[label]


def _loss(rows: Sequence[ResearchRow], weights: list[list[float]], bias: list[float], l2: float) -> float:
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        p = _softmax([sum(w * x for w, x in zip(class_w, row.feature_values)) + b for class_w, b in zip(weights, bias)])
        total -= log(max(p[_label_index(row.label)], 1e-15))
    penalty = l2 * sum(x * x for row in weights for x in row)
    return total / len(rows) + penalty


def fit(
    train: Sequence[ResearchRow],
    *,
    config: FitConfig,
    validation: Sequence[ResearchRow] = (),
) -> FitResult:
    if not train:
        raise ValueError("training set cannot be empty")
    dimensions = len(train[0].feature_values)
    if dimensions == 0 or any(len(row.feature_values) != dimensions for row in train):
        raise ValueError("training feature dimensions must be consistent")
    if config.learning_rate <= 0 or config.epochs <= 0 or config.l2 < 0:
        raise ValueError("invalid fit configuration")
    if len(config.classes) != 3:
        raise ValueError("the current fitter expects DOWN/FLAT/UP")

    weights = [[0.0] * dimensions for _ in config.classes]
    bias = [0.0] * len(config.classes)

    for _ in range(config.epochs):
        grad_w = [[0.0] * dimensions for _ in config.classes]
        grad_b = [0.0] * len(config.classes)
        for row in train:
            logits = [sum(w * x for w, x in zip(class_w, row.feature_values)) + b for class_w, b in zip(weights, bias)]
            probabilities = _softmax(logits)
            target = _label_index(row.label)
            for k in range(len(config.classes)):
                error = probabilities[k] - (1.0 if k == target else 0.0)
                grad_b[k] += error
                for j, x in enumerate(row.feature_values):
                    grad_w[k][j] += error * x + config.l2 * 2.0 * weights[k][j]
        scale = 1.0 / len(train)
        for k in range(len(config.classes)):
            bias[k] -= config.learning_rate * grad_b[k] * scale
            for j in range(dimensions):
                weights[k][j] -= config.learning_rate * grad_w[k][j] * scale

    params = ModelParameters(
        version=config.version,
        classes=config.classes,
        coefficients=tuple(tuple(row) for row in weights),
        intercepts=tuple(bias),
        regularization=config.l2,
    )
    val_loss = _loss(validation, weights, bias, config.l2) if validation else None
    val_accuracy = None
    if validation:
        correct = 0
        for row in validation:
            prediction = predict(
                prediction_id=f"validation:{row.row_id}",
                opportunity_id=row.row_id,
                prediction_time=row.decision_time,
                feature_snapshot_id=row.row_id,
                features=row.feature_values,
                parameters=params,
            )
            predicted_class = max(prediction.outputs, key=prediction.outputs.get)
            actual_class = config.classes[_label_index(row.label)]
            correct += predicted_class == actual_class
        val_accuracy = correct / len(validation)

    return FitResult(
        parameters=params,
        training_loss=_loss(train, weights, bias, config.l2),
        validation_loss=val_loss,
        validation_accuracy=val_accuracy,
    )
