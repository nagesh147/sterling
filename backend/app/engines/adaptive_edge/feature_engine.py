"""Causal, versioned feature snapshot boundary for Adaptive Edge.

This module intentionally contains no strategy-specific indicator formula. The
feature definitions must be promoted from the canonical strategy specification
with formula IDs before becoming executable strategy logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class FeatureStatus(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class FeatureProvenance:
    source_event_ids: tuple[str, ...] = ()
    formula_id: str | None = None
    formula_version: str | None = None


@dataclass(frozen=True)
class InstrumentContext:
    instrument_id: str
    instrument_version: str | None = None


@dataclass(frozen=True)
class FeatureInput:
    name: str
    value: float | None
    available_at: str
    status: FeatureStatus = FeatureStatus.VALID
    provenance: FeatureProvenance = FeatureProvenance()
    formula_version: str | None = None


@dataclass(frozen=True)
class FeatureSnapshot:
    snapshot_id: str
    strategy_version: str
    feature_set_version: str
    decision_time: str
    observation_cutoff_time: str
    values: Mapping[str, float | None]
    statuses: Mapping[str, FeatureStatus]
    available_at: Mapping[str, str]
    formula_ids: tuple[str, ...] = ()
    provenance: Mapping[str, FeatureProvenance] = None  # type: ignore[assignment]
    instrument_context: InstrumentContext | None = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            object.__setattr__(self, "provenance", {})
        names = set(self.values)
        if names != set(self.statuses) or names != set(self.available_at):
            raise ValueError("feature values, statuses, and availability must have identical keys")
        if set(self.provenance) != names:
            raise ValueError("every feature must have provenance")
        if self.instrument_context is None or not self.instrument_context.instrument_id:
            raise ValueError("canonical instrument identity is required")
        self.assert_causal(self.decision_time)

    def assert_causal(self, decision_time: str) -> None:
        """Fail closed if any feature claims availability after decision time."""
        for name, available_at in self.available_at.items():
            if available_at > decision_time:
                raise ValueError(f"lookahead detected for feature {name}: {available_at} > {decision_time}")

    def assert_compatible(
        self,
        *,
        strategy_version: str,
        feature_set_version: str,
    ) -> None:
        if self.strategy_version != strategy_version:
            raise ValueError("unsupported strategy version")
        if self.feature_set_version != feature_set_version:
            raise ValueError("unsupported feature-set version")


def build_feature_snapshot(
    *,
    snapshot_id: str,
    strategy_version: str,
    feature_set_version: str,
    observation_cutoff_time: str,
    inputs: list[FeatureInput],
    decision_time: str,
    instrument_context: InstrumentContext,
    formula_ids: Sequence[str] = (),
) -> FeatureSnapshot:
    values = {item.name: item.value for item in inputs}
    statuses = {item.name: item.status for item in inputs}
    available_at = {item.name: item.available_at for item in inputs}
    provenance = {item.name: item.provenance for item in inputs}
    snapshot = FeatureSnapshot(
        snapshot_id=snapshot_id,
        strategy_version=strategy_version,
        feature_set_version=feature_set_version,
        decision_time=decision_time,
        observation_cutoff_time=observation_cutoff_time,
        values=values,
        statuses=statuses,
        available_at=available_at,
        formula_ids=tuple(formula_ids),
        provenance=provenance,
        instrument_context=instrument_context,
    )
    return snapshot
