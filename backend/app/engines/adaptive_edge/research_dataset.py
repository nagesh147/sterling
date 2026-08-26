"""Research dataset contract for Adaptive Edge.

The dataset is a research artifact, not a live market-state container. Rows are
ordered by decision time and retain enough provenance to prove causal feature
availability and label separation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ResearchRow:
    row_id: str
    instrument: str
    decision_time: str
    feature_values: tuple[float, ...]
    feature_available_at: tuple[str, ...]
    label_end_time: str
    label: int

    def validate(self) -> None:
        if not self.row_id or not self.instrument:
            raise ValueError("row_id and instrument are required")
        if len(self.feature_values) != len(self.feature_available_at):
            raise ValueError("feature provenance dimensions do not match")
        if any(available_at > self.decision_time for available_at in self.feature_available_at):
            raise ValueError("feature availability occurs after decision time")
        if self.label_end_time <= self.decision_time:
            raise ValueError("label horizon must end after decision time")
        if self.label not in (-1, 0, 1):
            raise ValueError("label must be -1, 0, or 1")


def validate_dataset(rows: Sequence[ResearchRow]) -> tuple[ResearchRow, ...]:
    ordered = tuple(rows)
    for row in ordered:
        row.validate()
    for previous, current in zip(ordered, ordered[1:]):
        if current.decision_time < previous.decision_time:
            raise ValueError("dataset must be chronologically ordered")
    return ordered
