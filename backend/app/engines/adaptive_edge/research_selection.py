"""A50 research-selection and multiple-testing registry primitives.

A50 preserves the candidate population and selection process so a reported
winner cannot be detached from the research search that produced it. It does
not define a statistical correction, significance threshold, or promotion rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable


class ResearchSelectionError(ValueError):
    """Raised when an A50 registry invariant is violated."""


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    evaluation_id: str
    code_version: str
    feature_version: str
    label_version: str
    execution_version: str
    parameter_fingerprint: str
    result_fingerprint: str
    test_observed: bool = False
    selection_influenced: bool = False

    def __post_init__(self) -> None:
        for name in (
            "candidate_id", "evaluation_id", "code_version", "feature_version",
            "label_version", "execution_version", "parameter_fingerprint",
            "result_fingerprint",
        ):
            if not getattr(self, name).strip():
                raise ResearchSelectionError(f"{name} must not be empty")
        if self.selection_influenced and not self.test_observed:
            raise ResearchSelectionError("selection influence requires recorded test observation")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "evaluation_id": self.evaluation_id,
            "code_version": self.code_version,
            "feature_version": self.feature_version,
            "label_version": self.label_version,
            "execution_version": self.execution_version,
            "parameter_fingerprint": self.parameter_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "test_observed": self.test_observed,
            "selection_influenced": self.selection_influenced,
        }


@dataclass(frozen=True)
class SelectionDecision:
    selected_candidate_id: str
    selection_policy_id: str
    rationale: str
    decision_version: str

    def __post_init__(self) -> None:
        for name in (
            "selected_candidate_id", "selection_policy_id", "rationale", "decision_version"
        ):
            if not getattr(self, name).strip():
                raise ResearchSelectionError(f"{name} must not be empty")


@dataclass(frozen=True)
class ResearchSelectionRegistry:
    evaluation_id: str
    candidates: tuple[CandidateEvaluation, ...]
    decision: SelectionDecision | None
    registry_fingerprint: str

    @classmethod
    def build(
        cls,
        candidates: Iterable[CandidateEvaluation],
        decision: SelectionDecision | None = None,
    ) -> "ResearchSelectionRegistry":
        ordered = tuple(candidates)
        if not ordered:
            raise ResearchSelectionError("at least one candidate evaluation is required")
        evaluation_ids = {candidate.evaluation_id for candidate in ordered}
        if len(evaluation_ids) != 1:
            raise ResearchSelectionError("all candidates must belong to one evaluation_id")
        candidate_ids = [candidate.candidate_id for candidate in ordered]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ResearchSelectionError("duplicate candidate_id")
        if decision is not None and decision.selected_candidate_id not in set(candidate_ids):
            raise ResearchSelectionError("selected candidate is not present in registry")
        canonical = [item.canonical_payload() for item in sorted(ordered, key=lambda item: item.candidate_id)]
        payload = {
            "candidates": canonical,
            "decision": None if decision is None else {
                "selected_candidate_id": decision.selected_candidate_id,
                "selection_policy_id": decision.selection_policy_id,
                "rationale": decision.rationale,
                "decision_version": decision.decision_version,
            },
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=list)
        fingerprint = sha256(serialized.encode("utf-8")).hexdigest()
        return cls(evaluation_id=ordered[0].evaluation_id, candidates=ordered, decision=decision, registry_fingerprint=fingerprint)

    @property
    def test_observed_candidate_ids(self) -> tuple[str, ...]:
        return tuple(candidate.candidate_id for candidate in self.candidates if candidate.test_observed)

    @property
    def test_contaminated_candidate_ids(self) -> tuple[str, ...]:
        return tuple(candidate.candidate_id for candidate in self.candidates if candidate.test_observed and candidate.selection_influenced)

    @property
    def selection_population_size(self) -> int:
        return len(self.candidates)

    def final_test_eligible(self) -> bool:
        return not self.test_contaminated_candidate_ids
