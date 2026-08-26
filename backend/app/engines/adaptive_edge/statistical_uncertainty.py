"""A49 statistical-dependence and uncertainty primitives.

A49 records the dependence structure required before uncertainty is estimated.
It deliberately does not select a confidence level, estimator, bootstrap scheme,
or significance threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class StatisticalUncertaintyError(ValueError):
    """Raised when an A49 invariant is violated."""


class DependenceClass(str, Enum):
    IID_JUSTIFIED = "IID_JUSTIFIED"
    OVERLAPPING = "OVERLAPPING"
    SERIAL = "SERIAL"
    CLUSTERED = "CLUSTERED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DependenceUnit:
    unit_id: str
    cycle_id: str
    episode_id: str
    start_time: str
    end_time: str
    dependence_class: DependenceClass

    def __post_init__(self) -> None:
        for name in ("unit_id", "cycle_id", "episode_id", "start_time", "end_time"):
            if not getattr(self, name).strip():
                raise StatisticalUncertaintyError(f"{name} must not be empty")
        if self.end_time < self.start_time:
            raise StatisticalUncertaintyError("end_time must not precede start_time")


@dataclass(frozen=True)
class UncertaintySpecification:
    method_id: str
    dependence_assumption: DependenceClass
    justification: str
    version: str

    def __post_init__(self) -> None:
        for name in ("method_id", "justification", "version"):
            if not getattr(self, name).strip():
                raise StatisticalUncertaintyError(f"{name} must not be empty")
        if self.dependence_assumption is DependenceClass.UNKNOWN:
            raise StatisticalUncertaintyError("uncertainty cannot claim a known dependence assumption")


@dataclass(frozen=True)
class UncertaintyEvidence:
    evaluation_id: str
    evidence_fingerprint: str
    units: tuple[DependenceUnit, ...]
    specification: UncertaintySpecification | None = None

    @classmethod
    def build(
        cls,
        evaluation_id: str,
        evidence_fingerprint: str,
        units: Iterable[DependenceUnit],
    ) -> "UncertaintyEvidence":
        if not evaluation_id.strip() or not evidence_fingerprint.strip():
            raise StatisticalUncertaintyError("evaluation identity and evidence fingerprint are required")
        ordered = tuple(units)
        if not ordered:
            raise StatisticalUncertaintyError("at least one dependence unit is required")
        ids = [unit.unit_id for unit in ordered]
        if len(ids) != len(set(ids)):
            raise StatisticalUncertaintyError("duplicate dependence unit")
        return cls(evaluation_id=evaluation_id, evidence_fingerprint=evidence_fingerprint, units=ordered)

    @property
    def classes(self) -> tuple[DependenceClass, ...]:
        return tuple(sorted({unit.dependence_class for unit in self.units}, key=lambda item: item.value))

    @property
    def iid_justified(self) -> bool:
        return bool(self.classes) and self.classes == (DependenceClass.IID_JUSTIFIED,)

    def attach_specification(self, specification: UncertaintySpecification) -> "UncertaintyEvidence":
        if specification.dependence_assumption not in self.classes:
            raise StatisticalUncertaintyError("uncertainty assumption does not match observed dependence classes")
        return UncertaintyEvidence(
            evaluation_id=self.evaluation_id,
            evidence_fingerprint=self.evidence_fingerprint,
            units=self.units,
            specification=specification,
        )
