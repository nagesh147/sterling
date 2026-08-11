"""Calibration and promotion gates for Adaptive Edge probability models.

Research-only: calibration parameters are learned from validation data and are
never fitted on holdout observations. Promotion remains blocked unless every
pre-declared gate passes.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Sequence

from .probability_engine import ModelParameters, predict
from .research_dataset import ResearchRow


@dataclass(frozen=True)
class CalibrationConfig:
    version: str
    min_validation_rows: int = 30
    max_log_loss: float = 1.10
    min_accuracy: float = 0.34
    max_abs_calibration_error: float = 0.10


@dataclass(frozen=True)
class CalibrationResult:
    model_version: str
    temperature: float
    log_loss: float
    accuracy: float
    expected_calibration_error: float
    eligible: bool
    reasons: tuple[str, ...]


def _softmax(logits: Sequence[float]) -> tuple[float, ...]:
    peak = max(logits)
    weights = [__import__("math").exp(x - peak) for x in logits]
    total = sum(weights)
    return tuple(w / total for w in weights)


def _raw_probabilities(row: ResearchRow, params: ModelParameters, temperature: float) -> tuple[float, ...]:
    logits = []
    for coefficients, intercept in zip(params.coefficients, params.intercepts):
        logits.append((sum(w * x for w, x in zip(coefficients, row.feature_values)) + intercept) / temperature)
    return _softmax(logits)


def _metrics(rows: Sequence[ResearchRow], params: ModelParameters, temperature: float) -> tuple[float, float, float]:
    if not rows:
        return 0.0, 0.0, 0.0
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(10)]
    loss = 0.0
    correct = 0
    for row in rows:
        probabilities = _raw_probabilities(row, params, temperature)
        target = {-1: 0, 0: 1, 1: 2}[row.label]
        p = max(probabilities[target], 1e-15)
        loss -= log(p)
        prediction = max(range(len(probabilities)), key=probabilities.__getitem__)
        correct += prediction == target
        confidence = max(probabilities)
        bucket = min(9, int(confidence * 10))
        bins[bucket].append((confidence, prediction == target))
    ece = 0.0
    n = len(rows)
    for bucket in bins:
        if bucket:
            confidence = sum(x[0] for x in bucket) / len(bucket)
            accuracy = sum(x[1] for x in bucket) / len(bucket)
            ece += len(bucket) / n * abs(confidence - accuracy)
    return loss / n, correct / n, ece


def calibrate(
    validation: Sequence[ResearchRow],
    *,
    params: ModelParameters,
    config: CalibrationConfig,
) -> CalibrationResult:
    if len(validation) < config.min_validation_rows:
        return CalibrationResult(config.version, 1.0, float("inf"), 0.0, float("inf"), False, ("insufficient_validation_rows",))

    best_temperature = 1.0
    best_loss = float("inf")
    # Coarse deterministic grid; calibration must not silently optimize on holdout.
    for temperature in [0.50 + i * 0.05 for i in range(61)]:
        loss, _, _ = _metrics(validation, params, temperature)
        if loss < best_loss:
            best_loss = loss
            best_temperature = temperature

    loss, accuracy, ece = _metrics(validation, params, best_temperature)
    reasons: list[str] = []
    if loss > config.max_log_loss:
        reasons.append("validation_log_loss_too_high")
    if accuracy < config.min_accuracy:
        reasons.append("validation_accuracy_too_low")
    if ece > config.max_abs_calibration_error:
        reasons.append("calibration_error_too_high")
    return CalibrationResult(config.version, best_temperature, loss, accuracy, ece, not reasons, tuple(reasons))
