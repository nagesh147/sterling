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
from typing import Iterable, Sequence


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
    previous: EvaluationCycle | None = None
    for cycle in cycles:
        if previous is not None:
            if cycle.training.start < previous.training.start:
                raise EvaluationContractError("training windows must not move backward")
            if cycle.test.start <= previous.test.start:
                raise EvaluationContractError("test boundaries must advance strictly")
        previous = cycle


def eligible_training_observations(observations: Iterable[EvaluationObservation], cycle: EvaluationCycle) -> list[EvaluationObservation]:
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


def purge_for_boundary(observations: Iterable[EvaluationObservation], evaluation_boundary: TemporalSpan) -> tuple[list[EvaluationObservation], list[EvaluationObservation]]:
    safe: list[EvaluationObservation] = []
    purged: list[EvaluationObservation] = []
    for observation in observations:
        if observation.outcome_span is not None and observation.outcome_span.overlaps(evaluation_boundary):
            purged.append(observation)
        else:
            safe.append(observation)
    return safe, purged


def detect_overlapping_outcomes(observations: Sequence[EvaluationObservation]) -> list[tuple[str, str]]:
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
    episode_ids = {observation.independent_episode_id for observation in observations if observation.independent_episode_id is not None}
    return len(episode_ids)


def assign_observation(observation: EvaluationObservation, cycle: EvaluationCycle) -> ObservationDisposition:
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
    candidates: dict[str, CandidateSpec] = field(default_factory=dict)
    results: list[CandidateResult] = field(default_factory=list)
    test_use: list[TestUseEvent] = field(default_factory=list)

    def register_candidate(self, candidate: CandidateSpec) -> None:
        existing = self.candidates.get(candidate.candidate_id)
        if existing is not None and existing != candidate:
            raise EvaluationContractError(f"candidate_id {candidate.candidate_id!r} already identifies a different candidate")
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
            raise TestSetContaminatedError("final holdout result influenced selection; it is no longer an untouched test set")


def final_test_is_claim_eligible(registry: ResearchRegistry, holdout: FinalHoldout) -> bool:
    return holdout.status is HoldoutStatus.FROZEN and not registry.test_contaminated
