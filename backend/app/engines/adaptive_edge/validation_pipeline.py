"""Fail-closed validation orchestration for calibration, walk-forward and OOS evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .walk_forward import EvaluationCycle, EvaluationObservation, validate_walk_forward_sequence, detect_overlapping_outcomes


@dataclass(frozen=True)
class ValidationReport:
    walk_forward_valid: bool
    test_contamination_free: bool
    adversarial_valid: bool
    oos_valid: bool
    reasons: tuple[str, ...]

    @property
    def promotable(self) -> bool:
        return self.walk_forward_valid and self.test_contamination_free and self.adversarial_valid and self.oos_valid


def validate_evidence(*, cycles: Sequence[EvaluationCycle], test_observations: Sequence[EvaluationObservation], adversarial_failures: Sequence[str], oos_observations: Sequence[EvaluationObservation]) -> ValidationReport:
    reasons: list[str] = []
    try:
        validate_walk_forward_sequence(cycles)
        walk_forward_valid = bool(cycles)
    except Exception as exc:
        walk_forward_valid = False
        reasons.append(f"walk_forward_invalid:{type(exc).__name__}")

    overlaps = detect_overlapping_outcomes(test_observations)
    test_contamination_free = not overlaps
    if overlaps:
        reasons.append("test_outcome_overlap_detected")

    adversarial_valid = not adversarial_failures
    if adversarial_failures:
        reasons.append("adversarial_failures_present")

    oos_valid = bool(oos_observations)
    if not oos_valid:
        reasons.append("oos_evidence_missing")

    if not cycles:
        reasons.append("walk_forward_evidence_missing")
    return ValidationReport(walk_forward_valid, test_contamination_free, adversarial_valid, oos_valid, tuple(reasons))
