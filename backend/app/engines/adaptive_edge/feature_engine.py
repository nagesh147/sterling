"""Causal feature facade for Adaptive Edge.

A40 owns feature identity, availability, immutable snapshots, and provenance.
This module keeps the existing engine-facing construction API while delegating
those semantics to the lineage layer. It intentionally contains no
strategy-specific feature formula.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from .feature_lineage import (
    FeatureDefinition,
    FeatureInput as LineageFeatureInput,
    FeatureQuality,
    FeatureSnapshot,
    SourceReference,
    build_feature_snapshot as build_lineage_snapshot,
)


class FeatureInput:
    """Backward-compatible engine input using ISO-8601 availability timestamps."""

    def __init__(self, name: str, value: float, available_at: str) -> None:
        self.name = name
        self.value = value
        self.available_at = available_at


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    timestamp = datetime.fromisoformat(normalized)
    if timestamp.tzinfo is None:
        raise ValueError("feature timestamps must be timezone-aware ISO-8601 values")
    return timestamp.astimezone(timezone.utc)


def build_feature_snapshot(
    *,
    observation_time: str,
    inputs: list[FeatureInput],
    decision_time: str,
    formula_ids: Sequence[str] = (),
) -> FeatureSnapshot:
    """Build an A40 snapshot without inventing feature semantics.

    The compatibility API derives only infrastructure metadata from the supplied
    inputs. Callers that have canonical definitions should use
    ``feature_lineage.build_feature_snapshot`` directly.
    """
    decision = _parse_timestamp(decision_time)
    observation = _parse_timestamp(observation_time)
    lineage_inputs = [
        LineageFeatureInput(
            name=item.name,
            value=item.value,
            observation_time=observation,
            availability_time=_parse_timestamp(item.available_at),
            source=SourceReference(),
            quality=FeatureQuality.AVAILABLE,
        )
        for item in inputs
    ]
    definitions = {
        item.name: FeatureDefinition(
            feature_id=item.name,
            feature_definition_version="UNSPECIFIED",
            transformation_version="UNSPECIFIED",
            source_dataset_version="UNSPECIFIED",
            unit="UNSPECIFIED",
            semantic_definition="UNSPECIFIED — feature formula not defined by A40",
        )
        for item in inputs
    }
    return build_lineage_snapshot(
        snapshot_id=f"compat:{observation.isoformat()}:{decision.isoformat()}",
        observation_time=observation,
        decision_time=decision,
        inputs=lineage_inputs,
        definitions=definitions,
        formula_ids=formula_ids,
    )
