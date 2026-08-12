"""Provider-neutral inputs for execution-cost assessment.

This module intentionally does not estimate execution cost. A35 requires
reference, expected-execution, submitted, and fill prices to remain distinct,
and requires each market-price observation to carry provenance and freshness.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PriceType(str, Enum):
    REFERENCE = "REFERENCE"
    EXPECTED_EXECUTION = "EXPECTED_EXECUTION"
    SUBMITTED = "SUBMITTED"
    FILL = "FILL"


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class ExecutionCostInputError(ValueError):
    pass


@dataclass(frozen=True)
class PriceObservation:
    instrument_id: str
    price_type: PriceType
    value: float
    observation_timestamp_ms: int
    availability_timestamp_ms: int
    source: str
    source_version: str
    freshness: FreshnessState

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ExecutionCostInputError("instrument_id is required")
        if self.value <= 0:
            raise ExecutionCostInputError("price value must be positive")
        if self.observation_timestamp_ms < 0 or self.availability_timestamp_ms < 0:
            raise ExecutionCostInputError("timestamps must be non-negative")
        if self.availability_timestamp_ms < self.observation_timestamp_ms:
            raise ExecutionCostInputError("availability cannot precede observation")
        if not self.source or not self.source_version:
            raise ExecutionCostInputError("source and source_version are required")


@dataclass(frozen=True)
class ExecutionCostInputs:
    instrument_id: str
    decision_time_ms: int
    reference_price: Optional[PriceObservation] = None
    expected_execution_price: Optional[PriceObservation] = None
    submitted_order_price: Optional[PriceObservation] = None
    bid: Optional[PriceObservation] = None
    ask: Optional[PriceObservation] = None

    def validate_pre_trade(self) -> None:
        if not self.instrument_id:
            raise ExecutionCostInputError("instrument_id is required")
        if self.decision_time_ms < 0:
            raise ExecutionCostInputError("decision_time_ms must be non-negative")
        for observation in (
            self.reference_price,
            self.expected_execution_price,
            self.submitted_order_price,
            self.bid,
            self.ask,
        ):
            if observation is None:
                continue
            if observation.instrument_id != self.instrument_id:
                raise ExecutionCostInputError("observation instrument mismatch")
            if observation.availability_timestamp_ms > self.decision_time_ms:
                raise ExecutionCostInputError("pre-trade input uses future information")
            if observation.price_type == PriceType.FILL:
                raise ExecutionCostInputError("fill observations are not pre-trade inputs")

    def available_for_pre_trade(self) -> bool:
        try:
            self.validate_pre_trade()
            return True
        except ExecutionCostInputError:
            return False


@dataclass(frozen=True)
class ExecutionCostAssessmentBoundary:
    """Explicit unresolved boundary; no cost estimate is produced."""

    inputs: ExecutionCostInputs
    reason: str

    def __post_init__(self) -> None:
        if not self.reason:
            raise ExecutionCostInputError("unresolved boundary requires a reason")
        self.inputs.validate_pre_trade()
