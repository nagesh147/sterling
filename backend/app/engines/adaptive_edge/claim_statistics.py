"""A52 claim-level statistical validity primitives.

This module records the statistical correction policy required to interpret a
research claim. It deliberately does not choose a correction, threshold, or
p-value rule that is absent from the source specifications.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClaimStatisticsError(ValueError):
    """Raised when an A52 statistical-validity invariant is violated."""


class CorrectionStatus(str, Enum):
    UNRESOLVED = "unresolved"
    SPECIFIED = "specified"
    APPLIED = "applied"


@dataclass(frozen=True)
class StatisticalValidityContract:
    evaluation_id: str
    research_registry_fingerprint: str
    candidate_population_size: int
    correction_status: CorrectionStatus
    correction_method_id: str | None = None
    significance_level: float | None = None
    adjusted_claim: bool = False

    def __post_init__(self) -> None:
        if not self.evaluation_id.strip():
            raise ClaimStatisticsError("evaluation_id must not be empty")
        if not self.research_registry_fingerprint.strip():
            raise ClaimStatisticsError("research_registry_fingerprint must not be empty")
        if self.candidate_population_size < 1:
            raise ClaimStatisticsError("candidate_population_size must be >= 1")
        if self.correction_status is CorrectionStatus.UNRESOLVED:
            if self.correction_method_id is not None or self.adjusted_claim:
                raise ClaimStatisticsError("unresolved correction cannot produce an adjusted claim")
        elif not self.correction_method_id or not self.correction_method_id.strip():
            raise ClaimStatisticsError("specified/applied correction requires method identity")
        if self.significance_level is not None and not 0 < self.significance_level < 1:
            raise ClaimStatisticsError("significance_level must be between 0 and 1")
        if self.correction_status is CorrectionStatus.APPLIED and not self.adjusted_claim:
            raise ClaimStatisticsError("applied correction requires adjusted_claim=true")

    def claim_eligible(self) -> bool:
        """Whether the contract permits a statistically adjusted claim."""
        return self.correction_status is CorrectionStatus.APPLIED and self.adjusted_claim

    @classmethod
    def unresolved(
        cls,
        evaluation_id: str,
        research_registry_fingerprint: str,
        candidate_population_size: int,
    ) -> "StatisticalValidityContract":
        return cls(
            evaluation_id=evaluation_id,
            research_registry_fingerprint=research_registry_fingerprint,
            candidate_population_size=candidate_population_size,
            correction_status=CorrectionStatus.UNRESOLVED,
        )
