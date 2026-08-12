"""A40 feature availability, snapshot, and lineage primitives.

This module implements the causal feature infrastructure only. It deliberately
contains no Adaptive Edge feature formula. A feature becomes executable only
when its semantic definition, source, availability semantics, transformation,
and version are explicitly supplied by an upstream strategy artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence


class FeatureLineageError(ValueError):
    """Raised when a feature violates the A40 causal/lineage contract."""


class FeatureQuality(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    STALE = "STALE"
    INVALID = "INVALID"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class FeatureDefinition:
    feature_id: str
    feature_definition_version: str
    transformation_version: str
    source_dataset_version: str
    unit: str
    semantic_definition: str

    def __post_init__(self) -> None:
        for name in (
            "feature_id",
            "feature_definition_version",
            "transformation_version",
            "source_dataset_version",
            "unit",
            "semantic_definition",
        ):
            if not getattr(self, name).strip():
                raise FeatureLineageError(f"{name} must not be empty")


@dataclass(frozen=True)
class SourceReference:
    source_event_ids: tuple[str, ...] = ()
    source_dataset_versions: tuple[str, ...] = ()
    availability_times: tuple[datetime, ...] = ()

    def __post_init__(self) -> None:
        for value in self.availability_times:
            _require_aware(value, "availability time")


@dataclass(frozen=True)
class FeatureInput:
    """One dependency supplied to a feature transformation."""

    name: str
    value: float
    observation_time: datetime
    availability_time: datetime
    source: SourceReference = field(default_factory=SourceReference)
    quality: FeatureQuality = FeatureQuality.AVAILABLE

    def __post_init__(self) -> None:
        _require_aware(self.observation_time, "observation time")
        _require_aware(self.availability_time, "availability time")
        if self.availability_time < self.observation_time:
            # A source may publish later than observation, but not before the
            # observation itself in this canonical event model.
            raise FeatureLineageError(
                f"availability_time precedes observation_time for {self.name}"
            )


@dataclass(frozen=True)
class FeatureProvenance:
    feature_id: str
    feature_version: str
    snapshot_id: str
    decision_time: datetime
    source_event_ids: tuple[str, ...]
    source_dataset_versions: tuple[str, ...]
    transformation_version: str
    availability_watermark: datetime
    quality_state: FeatureQuality

    def __post_init__(self) -> None:
        _require_aware(self.decision_time, "decision time")
        _require_aware(self.availability_watermark, "availability watermark")
        if self.availability_watermark > self.decision_time:
            raise FeatureLineageError("availability watermark exceeds decision time")


@dataclass(frozen=True)
class FeatureSnapshot:
    """Immutable feature values plus their causal/provenance metadata."""

    snapshot_id: str
    observation_time: datetime
    decision_time: datetime
    values: Mapping[str, float]
    available_at: Mapping[str, datetime]
    definitions: Mapping[str, FeatureDefinition]
    provenance: tuple[FeatureProvenance, ...]
    source_versions: tuple[str, ...]
    transformation_versions: tuple[str, ...]
    availability_watermark: datetime
    quality_state: FeatureQuality
    formula_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_aware(self.observation_time, "observation time")
        _require_aware(self.decision_time, "decision time")
        _require_aware(self.availability_watermark, "availability watermark")
        if self.availability_watermark > self.decision_time:
            raise FeatureLineageError("snapshot watermark exceeds decision time")

        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(self, "available_at", MappingProxyType(dict(self.available_at)))
        object.__setattr__(self, "definitions", MappingProxyType(dict(self.definitions)))

        if set(self.values) != set(self.available_at):
            raise FeatureLineageError("values and availability keys must match")
        if set(self.values) != set(self.definitions):
            raise FeatureLineageError("values and definitions keys must match")

        for name, available_at in self.available_at.items():
            _require_aware(available_at, f"availability time for {name}")
            if available_at > self.decision_time:
                raise FeatureLineageError(
                    f"lookahead detected for feature {name}: "
                    f"{available_at.isoformat()} > {self.decision_time.isoformat()}"
                )

    def assert_causal(self, decision_time: datetime | None = None) -> None:
        boundary = decision_time or self.decision_time
        _require_aware(boundary, "decision time")
        for name, available_at in self.available_at.items():
            if available_at > boundary:
                raise FeatureLineageError(
                    f"lookahead detected for feature {name}: "
                    f"{available_at.isoformat()} > {boundary.isoformat()}"
                )

    def provenance_for(self, feature_id: str) -> FeatureProvenance:
        matches = [item for item in self.provenance if item.feature_id == feature_id]
        if len(matches) != 1:
            raise FeatureLineageError(
                f"expected exactly one provenance record for {feature_id}, got {len(matches)}"
            )
        return matches[0]


@dataclass(frozen=True)
class FeatureDependencyGraph:
    """Acyclic same-time dependency graph for feature definitions."""

    dependencies: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dependencies",
            MappingProxyType({key: tuple(value) for key, value in self.dependencies.items()}),
        )
        self.assert_acyclic()

    def assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise FeatureLineageError(f"circular feature dependency at {node}")
            if node in visited:
                return
            visiting.add(node)
            for dependency in self.dependencies.get(node, ()):
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in self.dependencies:
            visit(node)


def causal_feature_availability(inputs: Iterable[FeatureInput]) -> datetime:
    """Return max dependency availability, as required for multi-source features."""
    values = tuple(inputs)
    if not values:
        raise FeatureLineageError("feature requires at least one dependency")
    return max(item.availability_time for item in values)


def build_feature_snapshot(
    *,
    snapshot_id: str,
    decision_time: datetime,
    inputs: Sequence[FeatureInput],
    definitions: Mapping[str, FeatureDefinition],
    formula_ids: Sequence[str] = (),
    quality_state: FeatureQuality = FeatureQuality.AVAILABLE,
    source_versions: Sequence[str] = (),
    transformation_versions: Sequence[str] = (),
) -> FeatureSnapshot:
    """Construct an immutable, causally valid snapshot without computing a strategy formula."""
    if not snapshot_id.strip():
        raise FeatureLineageError("snapshot_id must not be empty")
    _require_aware(decision_time, "decision time")
    if not inputs:
        raise FeatureLineageError("feature snapshot requires at least one input")

    names = [item.name for item in inputs]
    if len(names) != len(set(names)):
        raise FeatureLineageError("feature input names must be unique")
    if set(names) != set(definitions):
        raise FeatureLineageError("every input must have exactly one feature definition")

    watermark = causal_feature_availability(inputs)
    if watermark > decision_time:
        raise FeatureLineageError(
            f"feature availability watermark exceeds decision time: "
            f"{watermark.isoformat()} > {decision_time.isoformat()}"
        )

    values = {item.name: item.value for item in inputs}
    available_at = {item.name: item.availability_time for item in inputs}
    source_event_ids = tuple(
        event_id
        for item in inputs
        for event_id in item.source.source_event_ids
    )
    dataset_versions = tuple(
        dict.fromkeys(
            [*source_versions]
            + [
                version
                for item in inputs
                for version in item.source.source_dataset_versions
            ]
        )
    )
    transformation = tuple(dict.fromkeys(transformation_versions))

    provenance = tuple(
        FeatureProvenance(
            feature_id=definitions[item.name].feature_id,
            feature_version=definitions[item.name].feature_definition_version,
            snapshot_id=snapshot_id,
            decision_time=decision_time,
            source_event_ids=tuple(item.source.source_event_ids),
            source_dataset_versions=tuple(item.source.source_dataset_versions),
            transformation_version=definitions[item.name].transformation_version,
            availability_watermark=item.availability_time,
            quality_state=item.quality,
        )
        for item in inputs
    )

    snapshot = FeatureSnapshot(
        snapshot_id=snapshot_id,
        observation_time=max(item.observation_time for item in inputs),
        decision_time=decision_time,
        values=values,
        available_at=available_at,
        definitions=definitions,
        provenance=provenance,
        source_versions=dataset_versions,
        transformation_versions=transformation,
        availability_watermark=watermark,
        quality_state=quality_state,
        formula_ids=tuple(formula_ids),
    )
    snapshot.assert_causal()
    return snapshot


def build_causal_rolling_window(
    observations: Sequence[FeatureInput],
    *,
    decision_time: datetime,
    lookback_seconds: int,
    include_boundary: bool = True,
) -> tuple[FeatureInput, ...]:
    """Select only causally available observations for a rolling feature window."""
    _require_aware(decision_time, "decision time")
    if lookback_seconds < 0:
        raise FeatureLineageError("lookback_seconds must be non-negative")
    start = decision_time.timestamp() - lookback_seconds
    result: list[FeatureInput] = []
    for item in observations:
        if item.availability_time > decision_time:
            continue
        available_ts = item.availability_time.timestamp()
        lower_ok = available_ts >= start if include_boundary else available_ts > start
        if lower_ok:
            result.append(item)
    return tuple(sorted(result, key=lambda item: item.availability_time))


def reconstruct_model_state(
    states: Sequence[tuple[datetime, object]],
    *,
    decision_time: datetime,
) -> object | None:
    """Return the latest prior state available at the decision boundary."""
    _require_aware(decision_time, "decision time")
    prior = [state for timestamp, state in states if _require_aware(timestamp, "state time") <= decision_time]
    return prior[-1] if prior else None


def _require_aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FeatureLineageError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)
