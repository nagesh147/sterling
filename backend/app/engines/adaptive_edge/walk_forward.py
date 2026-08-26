"""A39 walk-forward evaluation primitives for Adaptive Edge.

This module implements only the evaluation architecture that is already
specified. It deliberately does not choose target/horizon semantics,
window lengths, purge/embargo durations, statistical estimators, or promotion
thresholds that remain unresolved upstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterable, Sequence, TypeVar


class EvaluationContractError(ValueError):
    """Raised when an evaluation object violates the A39 contract."""


class TestSetContaminatedError(EvaluationContractError):
    """Raised when final-test evidence is allowed to influence selection."""


class ObservationDisposition(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    INELIGIBLE = "ineligible"
    UNASSIGNED = "unassigned"


class HoldoutStatus(str, Enum):
    OPEN = "open"
    FROZEN = "frozen"
    CONTAMINATED = "contaminated"


@dataclass(frozen=True, order=True)
class TemporalSpan:
    """Half-open temporal interval [start, end)."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise EvaluationContractError("temporal span must have end > start")

    def contains(self, value: datetime) -> bool:
        return self.start <= value < self.end

    def overlaps(self, other: "TemporalSpan") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class EvaluationObservation:
    """Decision-linked observation used by the A38/A39 temporal boundary."""

    observation_id: str
    decision_time: datetime
    feature_available_time: datetime
    label_maturity_time: datetime | None
    outcome_span: TemporalSpan | None = None
    independent_episode_id: str | None = None

    def feature_causally_available(self) -> bool:
        return self.feature_available_time <= self.decision_time

    def label_mature_at(self, cutoff: datetime) -> bool:
        return self.label_maturity_time is not None and self.label_maturity_time <= cutoff


@dataclass(frozen=True)
class EvaluationCycle:
    """One causal train -> validation -> promotion -> test cycle.

    Purge/embargo are explicit optional boundaries. No duration is inferred.
    """

    cycle_id: str
    training: TemporalSpan
    validation: TemporalSpan
    test: TemporalSpan
    purge: TemporalSpan | None = None
    embargo: TemporalSpan | None = None
    feature_policy_version: str = "UNKNOWN"
    label_policy_version: str = "UNKNOWN"
    model_policy_version: str = "UNKNOWN"
    promotion_time: datetime | None = None

    def __post_init__(self) -> None:
        if self.training.end > self.validation.start:
            raise EvaluationContractError("training and validation windows overlap")
        if self.validation.end > self.test.start:
            raise EvaluationContractError("validation and test windows overlap")
        if self.promotion_time is not None:
            if self.promotion_time < self.validation.end:
                raise EvaluationContractError("promotion must occur after validation ends")
            if self.promotion_time >= self.test.start:
                raise EvaluationContractError("promotion must occur before test begins")
        for name, boundary in (("purge", self.purge), ("embargo", self.embargo)):
            if boundary is not None and boundary.overlaps(self.validation):
                raise EvaluationContractError(f"{name} boundary cannot overlap validation")

    @property
    def training_cutoff(self) -> datetime:
        return self.training.end


def validate_walk_forward_sequence(cycles: Sequence[EvaluationCycle]) -> None:
    """Require strictly forward progression of cycle test boundaries."""

    previous: EvaluationCycle | None = None
    for cycle in cycles:
        if previous is not None:
            if cycle.training.start < previous.training.start:
                raise EvaluationContractError("training windows must not move backward")
            if cycle.test.start <= previous.test.start:
                raise EvaluationContractError("test boundaries must advance strictly")
        previous = cycle


def eligible_training_observations(
    observations: Iterable[EvaluationObservation],
    cycle: EvaluationCycle,
) -> list[EvaluationObservation]:
    """Apply A38 causal eligibility at the cycle's training cutoff.

    This intentionally does not infer a label horizon or purge duration.
    """

    eligible: list[EvaluationObservation] = []
    for observation in observations:
        if not cycle.training.contains(observation.decision_time):
            continue
        if not observation.feature_causally_available():
            continue
        if not observation.label_mature_at(cycle.training_cutoff):
            continue
        eligible.append(observation)
    return eligible


def purge_for_boundary(
    observations: Iterable[EvaluationObservation],
    evaluation_boundary: TemporalSpan,
) -> tuple[list[EvaluationObservation], list[EvaluationObservation]]:
    """Split observations whose resolved outcome span crosses a boundary.

    If no outcome span is supplied, the observation is not purged here because
    A26 has not yet defined the target/horizon. Final evaluation must supply
    the resolved outcome spans before treating purge as complete.
    """

    safe: list[EvaluationObservation] = []
    purged: list[EvaluationObservation] = []
    for observation in observations:
        if observation.outcome_span is not None and observation.outcome_span.overlaps(evaluation_boundary):
            purged.append(observation)
        else:
            safe.append(observation)
    return safe, purged


def detect_overlapping_outcomes(
    observations: Sequence[EvaluationObservation],
) -> list[tuple[str, str]]:
    """Return observation pairs whose resolved outcome spans overlap."""

    spans = [observation for observation in observations if observation.outcome_span is not None]
    overlaps: list[tuple[str, str]] = []
    for index, left in enumerate(spans):
        assert left.outcome_span is not None
        for right in spans[index + 1 :]:
            assert right.outcome_span is not None
            if left.outcome_span.overlaps(right.outcome_span):
                overlaps.append((left.observation_id, right.observation_id))
    return overlaps


def count_independent_episodes(observations: Iterable[EvaluationObservation]) -> int:
    """Count explicit independent economic episodes without assuming IID data."""

    episode_ids = {
        observation.independent_episode_id
        for observation in observations
        if observation.independent_episode_id is not None
    }
    return len(episode_ids)


def assign_observation(
    observation: EvaluationObservation,
    cycle: EvaluationCycle,
) -> ObservationDisposition:
    """Assign by decision boundary while enforcing A38 training eligibility."""

    if cycle.training.contains(observation.decision_time):
        if observation.feature_causally_available() and observation.label_mature_at(cycle.training_cutoff):
            return ObservationDisposition.TRAIN
        return ObservationDisposition.INELIGIBLE
    if cycle.validation.contains(observation.decision_time):
        return ObservationDisposition.VALIDATION
    if cycle.test.contains(observation.decision_time):
        return ObservationDisposition.TEST
    return ObservationDisposition.UNASSIGNED


@dataclass(frozen=True)
class CandidateSpec:
    """Immutable identity of one researched candidate."""

    candidate_id: str
    code_version: str
    feature_version: str
    label_version: str
    parameter_set: tuple[tuple[str, str], ...] = ()
    execution_model_version: str = "UNKNOWN"
    training_boundary: str = "UNKNOWN"
    validation_boundary: str = "UNKNOWN"
    selection_rationale: str = ""


@dataclass(frozen=True)
class CandidateResult:
    candidate_id: str
    cycle_id: str
    metrics: tuple[tuple[str, float], ...] = ()
    selected: bool = False


@dataclass(frozen=True)
class TestUseEvent:
    candidate_id: str
    cycle_id: str
    purpose: str
    influenced_selection: bool


@dataclass
class ResearchRegistry:
    """Append-only research identity for candidates and evaluation results."""

    candidates: dict[str, CandidateSpec] = field(default_factory=dict)
    results: list[CandidateResult] = field(default_factory=list)
    test_use: list[TestUseEvent] = field(default_factory=list)

    def register_candidate(self, candidate: CandidateSpec) -> None:
        existing = self.candidates.get(candidate.candidate_id)
        if existing is not None and existing != candidate:
            raise EvaluationContractError(
                f"candidate_id {candidate.candidate_id!r} already identifies a different candidate"
            )
        self.candidates[candidate.candidate_id] = candidate

    def record_result(self, result: CandidateResult) -> None:
        if result.candidate_id not in self.candidates:
            raise EvaluationContractError("candidate must be registered before recording a result")
        self.results.append(result)

    def record_test_use(self, event: TestUseEvent) -> None:
        if event.candidate_id not in self.candidates:
            raise EvaluationContractError("test use references an unknown candidate")
        self.test_use.append(event)

    @property
    def test_contaminated(self) -> bool:
        return any(event.influenced_selection for event in self.test_use)


@dataclass
class FinalHoldout:
    """State machine protecting the final untouched evaluation boundary."""

    status: HoldoutStatus = HoldoutStatus.OPEN
    candidate_id: str | None = None
    selection_frozen_at: datetime | None = None

    def freeze(self, candidate_id: str, frozen_at: datetime) -> None:
        if self.status is HoldoutStatus.CONTAMINATED:
            raise TestSetContaminatedError("contaminated holdout cannot be frozen")
        if self.status is HoldoutStatus.FROZEN:
            raise EvaluationContractError("final holdout is already frozen")
        self.candidate_id = candidate_id
        self.selection_frozen_at = frozen_at
        self.status = HoldoutStatus.FROZEN

    def record_use(self, *, influenced_selection: bool) -> None:
        if self.status is HoldoutStatus.OPEN:
            raise EvaluationContractError("final holdout cannot be used before selection is frozen")
        if influenced_selection:
            self.status = HoldoutStatus.CONTAMINATED
            raise TestSetContaminatedError(
                "final holdout result influenced selection; it is no longer an untouched test set"
            )


def final_test_is_claim_eligible(
    registry: ResearchRegistry,
    holdout: FinalHoldout,
) -> bool:
    """Return whether the test boundary remains eligible as final evidence."""

    return holdout.status is HoldoutStatus.FROZEN and not registry.test_contaminated


_Row = TypeVar("_Row")


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold: train, then validate, then hold out.

    The purged and embargoed rows are kept rather than discarded so a fold can
    account for every row in its window — you can see what was dropped and why,
    instead of inferring it from a gap in the indices.
    """

    train: tuple[_Row, ...]
    validation: tuple[_Row, ...]
    holdout: tuple[_Row, ...]
    purged: tuple[_Row, ...] = ()
    embargoed: tuple[_Row, ...] = ()


def build_folds(
    rows: Sequence[_Row],
    *,
    train_size: int,
    validation_size: int,
    holdout_size: int,
    purge_rows: int = 0,
    embargo_rows: int = 0,
) -> tuple[Fold, ...]:
    """Cut `rows` into non-overlapping train/validation/holdout folds.

    Rows must already be in chronological order — `validate_dataset` is what
    establishes that, and this function trusts it rather than re-sorting, so a
    caller cannot quietly launder an out-of-order dataset through here.

    Each window is laid out strictly forward in time:

        [ train ][ purge ][ validation ][ embargo ][ holdout ]

    The purge drops the rows straddling the train/validation boundary and the
    embargo drops those straddling validation/holdout. Both exist because a
    label is measured over a window that extends past its own decision time: a
    row decided just before a boundary is still resolving after it, so training
    on it leaks the outcome the next segment is supposed to be judged on. The
    gaps are the width of that overlap.

    Windows do not overlap. A row appears in at most one fold, so scores across
    folds are not correlated through shared rows, and a trailing remainder too
    short for a full window is left out rather than yielding a short fold whose
    segments would not mean the same thing.
    """
    if train_size < 1 or validation_size < 1 or holdout_size < 1:
        raise ValueError("train, validation and holdout sizes must each be at least 1")
    if purge_rows < 0 or embargo_rows < 0:
        raise ValueError("purge and embargo sizes cannot be negative")

    window = train_size + purge_rows + validation_size + embargo_rows + holdout_size
    folds: list[Fold] = []

    for start in range(0, len(rows) - window + 1, window):
        cut = start + train_size
        purge_end = cut + purge_rows
        validation_end = purge_end + validation_size
        embargo_end = validation_end + embargo_rows
        folds.append(
            Fold(
                train=tuple(rows[start:cut]),
                purged=tuple(rows[cut:purge_end]),
                validation=tuple(rows[purge_end:validation_end]),
                embargoed=tuple(rows[validation_end:embargo_end]),
                holdout=tuple(rows[embargo_end:embargo_end + holdout_size]),
            )
        )

    return tuple(folds)
