"""Model-selection gate for walk-forward Adaptive Edge research.

Selection scores validation folds only. Holdout results are accepted only after
a configuration has been frozen, preventing selection leakage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .calibration import CalibrationResult


@dataclass(frozen=True)
class CandidateModel:
    model_id: str
    fit_version: str
    calibration: CalibrationResult
    validation_net_value: float
    validation_drawdown: float


@dataclass(frozen=True)
class SelectionResult:
    selected_model_id: str | None
    frozen: bool
    reasons: tuple[str, ...]


def select_model(
    candidates: Sequence[CandidateModel],
    *,
    min_validation_net_value: float = 0.0,
    max_validation_drawdown: float = 0.20,
) -> SelectionResult:
    eligible = [
        c for c in candidates
        if c.calibration.eligible
        and c.validation_net_value >= min_validation_net_value
        and c.validation_drawdown <= max_validation_drawdown
    ]
    if not eligible:
        return SelectionResult(None, False, ("no_validation_eligible_model",))
    selected = max(eligible, key=lambda c: (c.validation_net_value, -c.validation_drawdown))
    return SelectionResult(selected.model_id, True, ())
