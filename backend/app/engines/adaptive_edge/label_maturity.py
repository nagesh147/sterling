"""A38 causal label-maturity and learning-boundary primitives.

The implementation is intentionally limited to semantics frozen by A38. It
cannot construct a strategy label because A26 target/horizon semantics remain
unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LabelMaturityError(ValueError):
    """Raised when a label violates A38 temporal/lineage constraints."""


class OutcomeState(str, Enum):
    OBSERVED = "OUTCOME_OBSERVED"
    MATURE = "OUTCOME_MATURE"
    LABEL_CONSTRUCTED = "LABEL_CONSTRUCTED"
    TRAINING_ELIGIBLE = "TRAINING_ELIGIBLE"
    TRAINING_USED = "TRAINING_USED"


@dataclass(frozen=True)
class DecisionReference:
    decision_id: str
    decision_time_ms: int
    strategy_version: str
    feature_snapshot_id: str
    prediction_version: str
    economic_assessment_id: str
    eligibility_id: str
    risk_authorization_id: str
    instrument_id: str


@dataclass(frozen=True)
class OutcomeObservation:
    decision_id: str
    observed_at_ms: int
    maturity_at_ms: int | None
    state: OutcomeState = OutcomeState.OBSERVED

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise LabelMaturityError("decision_id must not be empty")
        if self.observed_at_ms < 0:
            raise LabelMaturityError("observed_at_ms must be non-negative")
        if self.maturity_at_ms is not None:
            if self.maturity_at_ms < self.observed_at_ms:
                raise LabelMaturityError("maturity cannot precede observation")
            if self.state not in {
                OutcomeState.MATURE,
                OutcomeState.LABEL_CONSTRUCTED,
                OutcomeState.TRAINING_ELIGIBLE,
                OutcomeState.TRAINING_USED,
            }:
                raise LabelMaturityError("maturity timestamp requires a mature state")


@dataclass(frozen=True)
class MatureLabel:
    decision_id: str
    label_policy_version: str
    label_maturity_time_ms: int

    def __post_init__(self) -> None:
        if not self.decision_id.strip():
            raise LabelMaturityError("decision_id must not be empty")
        if not self.label_policy_version.strip():
            raise LabelMaturityError("label_policy_version must not be empty")
        if self.label_maturity_time_ms < 0:
            raise LabelMaturityError("label_maturity_time_ms must be non-negative")


def validate_feature_availability(
    feature_available_time_ms: int,
    decision_time_ms: int,
) -> None:
    """Enforce the A38 causal feature-availability boundary."""
    if feature_available_time_ms > decision_time_ms:
        raise LabelMaturityError(
            "feature_available_time cannot be after decision_time"
        )


def validate_decision_lineage(
    decision: DecisionReference,
    outcome: OutcomeObservation,
) -> None:
    """Require an outcome to reference the immutable originating decision."""
    if outcome.decision_id != decision.decision_id:
        raise LabelMaturityError("outcome must reference its originating decision")
    if outcome.observed_at_ms < decision.decision_time_ms:
        raise LabelMaturityError("outcome cannot precede its decision")


def construct_mature_label(
    decision: DecisionReference,
    outcome: OutcomeObservation,
    label_policy_version: str,
    as_of_ms: int,
) -> MatureLabel:
    """Construct only the maturity envelope, not an unresolved strategy label."""
    validate_decision_lineage(decision, outcome)
    if outcome.maturity_at_ms is None:
        raise LabelMaturityError("outcome is not mature")
    if outcome.maturity_at_ms > as_of_ms:
        raise LabelMaturityError("label is not mature at the supplied cutoff")
    if not label_policy_version.strip():
        raise LabelMaturityError("label_policy_version must not be empty")

    return MatureLabel(
        decision_id=decision.decision_id,
        label_policy_version=label_policy_version,
        label_maturity_time_ms=outcome.maturity_at_ms,
    )


def training_eligible(label: MatureLabel, training_cutoff_ms: int) -> bool:
    """A38 training eligibility: label maturity must precede the cutoff."""
    if training_cutoff_ms < 0:
        raise LabelMaturityError("training_cutoff_ms must be non-negative")
    return label.label_maturity_time_ms <= training_cutoff_ms
