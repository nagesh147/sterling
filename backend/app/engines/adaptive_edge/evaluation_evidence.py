"""A48 cycle-level evaluation evidence aggregation primitives.

A48 preserves every walk-forward cycle as an auditable evidence unit before
any downstream aggregation or statistical interpretation. It does not define
performance metrics, statistical thresholds, target horizons, or promotion
policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable


class EvaluationEvidenceError(ValueError):
    """Raised when an A48 evidence invariant is violated."""


@dataclass(frozen=True)
class CycleEvaluationResult:
    cycle_id: str
    evaluation_id: str
    candidate_id: str
    code_version: str
    feature_version: str
    label_version: str
    execution_version: str
    train_boundary_id: str
    validation_boundary_id: str
    test_boundary_id: str
    observation_count: int
    independent_episode_count: int
    excluded_observation_count: int = 0
    exclusion_reasons: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str], ...] = ()
    contaminated: bool = False
    result_fingerprint: str = ""

    def __post_init__(self) -> None:
        required = (
            "cycle_id", "evaluation_id", "candidate_id", "code_version",
            "feature_version", "label_version", "execution_version",
            "train_boundary_id", "validation_boundary_id", "test_boundary_id",
        )
        for name in required:
            if not getattr(self, name).strip():
                raise EvaluationEvidenceError(f"{name} must not be empty")
        if self.observation_count < 0 or self.independent_episode_count < 0:
            raise EvaluationEvidenceError("observation counts must be non-negative")
        if self.excluded_observation_count < 0:
            raise EvaluationEvidenceError("excluded_observation_count must be non-negative")
        if self.excluded_observation_count > self.observation_count:
            raise EvaluationEvidenceError("excluded observations cannot exceed observations")
        if self.independent_episode_count > self.observation_count:
            raise EvaluationEvidenceError("independent episodes cannot exceed observations")
        if self.contaminated and not self.result_fingerprint.strip():
            raise EvaluationEvidenceError("contaminated cycles still require result lineage")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "cycle_id": self.cycle_id,
            "evaluation_id": self.evaluation_id,
            "candidate_id": self.candidate_id,
            "code_version": self.code_version,
            "feature_version": self.feature_version,
            "label_version": self.label_version,
            "execution_version": self.execution_version,
            "train_boundary_id": self.train_boundary_id,
            "validation_boundary_id": self.validation_boundary_id,
            "test_boundary_id": self.test_boundary_id,
            "observation_count": self.observation_count,
            "independent_episode_count": self.independent_episode_count,
            "excluded_observation_count": self.excluded_observation_count,
            "exclusion_reasons": self.exclusion_reasons,
            "metrics": self.metrics,
            "contaminated": self.contaminated,
            "result_fingerprint": self.result_fingerprint,
        }


@dataclass(frozen=True)
class EvaluationEvidenceSet:
    evaluation_id: str
    cycles: tuple[CycleEvaluationResult, ...]
    fingerprint: str

    @classmethod
    def build(cls, cycles: Iterable[CycleEvaluationResult]) -> "EvaluationEvidenceSet":
        ordered = tuple(cycles)
        if not ordered:
            raise EvaluationEvidenceError("at least one cycle is required")
        ids = [cycle.cycle_id for cycle in ordered]
        if len(ids) != len(set(ids)):
            raise EvaluationEvidenceError("duplicate cycle_id")
        evaluation_ids = {cycle.evaluation_id for cycle in ordered}
        if len(evaluation_ids) != 1:
            raise EvaluationEvidenceError("all cycles must belong to one evaluation_id")
        canonical = [cycle.canonical_payload() for cycle in sorted(ordered, key=lambda item: item.cycle_id)]
        serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=list)
        fingerprint = sha256(serialized.encode("utf-8")).hexdigest()
        return cls(evaluation_id=ordered[0].evaluation_id, cycles=ordered, fingerprint=fingerprint)

    @property
    def contaminated_cycle_ids(self) -> tuple[str, ...]:
        return tuple(cycle.cycle_id for cycle in self.cycles if cycle.contaminated)

    @property
    def total_observations(self) -> int:
        return sum(cycle.observation_count for cycle in self.cycles)

    @property
    def total_independent_episodes(self) -> int:
        return sum(cycle.independent_episode_count for cycle in self.cycles)

    @property
    def total_excluded_observations(self) -> int:
        return sum(cycle.excluded_observation_count for cycle in self.cycles)
