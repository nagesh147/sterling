"""Causal feature layer for Adaptive Edge.

This module intentionally contains no strategy-specific indicator formula. The
feature definitions must be promoted from the canonical strategy specification
with formula IDs before becoming executable strategy logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FeatureInput:
    name: str
    value: float
    available_at: str


@dataclass(frozen=True)
class FeatureSnapshot:
    observation_time: str
    values: Mapping[str, float]
    available_at: Mapping[str, str]
    formula_ids: tuple[str, ...] = ()
    quality: str = "unknown"

    def assert_causal(self, decision_time: str) -> None:
        """Fail closed if any feature claims availability after decision time.

        ISO-8601 timestamps are required by the contract. The strategy layer
        should normalize them before constructing this snapshot.
        """
        for name, available_at in self.available_at.items():
            if available_at > decision_time:
                raise ValueError(f"lookahead detected for feature {name}: {available_at} > {decision_time}")


def build_feature_snapshot(
    *,
    observation_time: str,
    inputs: list[FeatureInput],
    decision_time: str,
    formula_ids: Sequence[str] = (),
) -> FeatureSnapshot:
    values = {item.name: item.value for item in inputs}
    available_at = {item.name: item.available_at for item in inputs}
    snapshot = FeatureSnapshot(
        observation_time,
        values,
        available_at,
        formula_ids=tuple(formula_ids),
    )
    snapshot.assert_causal(decision_time)
    return snapshot
