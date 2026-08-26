"""Explicit V2.1 probability calibration boundary.

V2.1 selects temperature scaling as its calibration method. Temperature is a
research parameter fitted only on the validation partition; no holdout labels
are accepted by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Sequence


class CalibrationError(ValueError):
    pass


@dataclass(frozen=True)
class CalibrationConfig:
    minimum_temperature: float = 0.25
    maximum_temperature: float = 4.0
    grid_points: int = 151

    def __post_init__(self) -> None:
        if self.minimum_temperature <= 0 or self.maximum_temperature < self.minimum_temperature or self.grid_points < 2:
            raise CalibrationError("invalid calibration configuration")


@dataclass(frozen=True)
class CalibrationResult:
    temperature: float
    validation_log_loss: float


def temperature_scale(logits: Sequence[float], temperature: float) -> tuple[float, ...]:
    if not logits or temperature <= 0:
        raise CalibrationError("logits must be non-empty and temperature positive")
    pivot = max(logits)
    weights = [exp((value - pivot) / temperature) for value in logits]
    total = sum(weights)
    return tuple(weight / total for weight in weights)


def _log_loss(logit_rows: Sequence[Sequence[float]], labels: Sequence[int], temperature: float) -> float:
    if len(logit_rows) != len(labels) or not logit_rows:
        raise CalibrationError("validation logits and labels must be aligned and non-empty")
    total = 0.0
    for logits, label in zip(logit_rows, labels):
        if label < 0 or label >= len(logits):
            raise CalibrationError("label outside calibration class range")
        probabilities = temperature_scale(logits, temperature)
        total -= log(max(probabilities[label], 1e-300))
    return total / len(labels)


def fit_temperature(
    *,
    validation_logits: Sequence[Sequence[float]],
    validation_labels: Sequence[int],
    config: CalibrationConfig,
) -> CalibrationResult:
    """Choose the validation-log-loss-minimizing temperature by deterministic grid search."""
    if len(validation_logits) != len(validation_labels) or not validation_logits:
        raise CalibrationError("validation logits and labels must be aligned and non-empty")
    step = (config.maximum_temperature - config.minimum_temperature) / (config.grid_points - 1)
    candidates = [config.minimum_temperature + index * step for index in range(config.grid_points)]
    scored = [(temperature, _log_loss(validation_logits, validation_labels, temperature)) for temperature in candidates]
    return CalibrationResult(min(scored, key=lambda item: (item[1], item[0]))[0], min(scored, key=lambda item: (item[1], item[0]))[1])
