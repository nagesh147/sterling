"""A41 prediction and decision-input boundary contracts.

This module intentionally implements identity and causal linkage only. It does
not choose a model family, target, probability semantics, calibration method,
or threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping


class PredictionContractError(ValueError):
    """Raised when an A41 prediction boundary invariant is violated."""


class OutputType(str, Enum):
    SCORE = "score"
    PROBABILITY = "probability"
    RAW = "raw"


@dataclass(frozen=True)
class PredictionProvenance:
    feature_snapshot_id: str
    model_version: str
    model_state_version: str
    calibration_version: str | None


@dataclass(frozen=True)
class PredictionRecord:
    prediction_id: str
    decision_time: datetime
    feature_snapshot_id: str
    model_version: str
    model_state_version: str
    raw_output: float
    output_type: OutputType
    calibration_version: str | None = None
    calibrated_output: float | None = None
    provenance: PredictionProvenance | None = None

    def __post_init__(self) -> None:
        if not self.prediction_id.strip():
            raise PredictionContractError("prediction_id must not be empty")
        if not self.feature_snapshot_id.strip():
            raise PredictionContractError("feature_snapshot_id must not be empty")
        if not self.model_version.strip():
            raise PredictionContractError("model_version must not be empty")
        if not self.model_state_version.strip():
            raise PredictionContractError("model_state_version must not be empty")
        _require_aware(self.decision_time)
        if not isfinite(self.raw_output):
            raise PredictionContractError("raw_output must be finite")
        if self.output_type is OutputType.PROBABILITY and not 0.0 <= self.raw_output <= 1.0:
            raise PredictionContractError("probability output must be within [0, 1]")
        if self.calibrated_output is not None:
            if not isfinite(self.calibrated_output):
                raise PredictionContractError("calibrated_output must be finite")
            if self.calibration_version is None:
                raise PredictionContractError("calibrated_output requires calibration_version")
            if not 0.0 <= self.calibrated_output <= 1.0:
                raise PredictionContractError("calibrated probability must be within [0, 1]")
        if self.provenance is not None:
            if self.provenance.feature_snapshot_id != self.feature_snapshot_id:
                raise PredictionContractError("prediction provenance feature snapshot mismatch")
            if self.provenance.model_version != self.model_version:
                raise PredictionContractError("prediction provenance model version mismatch")
            if self.provenance.model_state_version != self.model_state_version:
                raise PredictionContractError("prediction provenance model state mismatch")


@dataclass(frozen=True)
class DecisionInput:
    prediction_id: str
    prediction_type: OutputType
    prediction_value: float
    calibration_version: str | None
    feature_snapshot_id: str
    economic_context_reference: str | None
    model_version: str
    decision_time: datetime

    def __post_init__(self) -> None:
        if not self.prediction_id.strip():
            raise PredictionContractError("prediction_id must not be empty")
        if not self.feature_snapshot_id.strip():
            raise PredictionContractError("feature_snapshot_id must not be empty")
        if not self.model_version.strip():
            raise PredictionContractError("model_version must not be empty")
        if not isfinite(self.prediction_value):
            raise PredictionContractError("prediction_value must be finite")
        if self.prediction_type is OutputType.PROBABILITY and not 0.0 <= self.prediction_value <= 1.0:
            raise PredictionContractError("probability decision input must be within [0, 1]")
        _require_aware(self.decision_time)


def build_decision_input(prediction: PredictionRecord, *, economic_context_reference: str | None = None) -> DecisionInput:
    """Create the downstream input without applying eligibility or trade logic."""
    value = prediction.calibrated_output if prediction.calibrated_output is not None else prediction.raw_output
    output_type = OutputType.PROBABILITY if prediction.calibrated_output is not None else prediction.output_type
    return DecisionInput(
        prediction_id=prediction.prediction_id,
        prediction_type=output_type,
        prediction_value=value,
        calibration_version=prediction.calibration_version,
        feature_snapshot_id=prediction.feature_snapshot_id,
        economic_context_reference=economic_context_reference,
        model_version=prediction.model_version,
        decision_time=prediction.decision_time,
    )


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PredictionContractError("decision_time must be timezone-aware")
