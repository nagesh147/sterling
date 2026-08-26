from datetime import datetime, timedelta, timezone

import pytest

from app.engines.adaptive_edge.feature_lineage import (
    FeatureDefinition,
    FeatureDependencyGraph,
    FeatureInput,
    FeatureLineageError,
    FeatureQuality,
    SourceReference,
    build_causal_rolling_window,
    build_feature_snapshot,
    causal_feature_availability,
    reconstruct_model_state,
)

UTC = timezone.utc


def ts(minutes: int) -> datetime:
    return datetime(2026, 8, 12, 9, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def definition(name: str) -> FeatureDefinition:
    return FeatureDefinition(name, "1.0.0", "transform-1", "truedata-v1", "price", f"test feature {name}")


def inp(name: str, availability_minute: int, *, observation_minute: int = 0) -> FeatureInput:
    return FeatureInput(name, 1.0, ts(observation_minute), ts(availability_minute), SourceReference((f"evt-{name}",), ("truedata-v1",), (ts(availability_minute),)))


def test_multi_source_availability_is_latest_dependency():
    assert causal_feature_availability((inp("a", 1), inp("b", 4), inp("c", 2))) == ts(4)


def test_snapshot_rejects_future_availability():
    with pytest.raises(FeatureLineageError, match="watermark exceeds decision time"):
        build_feature_snapshot(snapshot_id="snap-1", decision_time=ts(10), inputs=(inp("a", 1), inp("future", 11)), definitions={"a": definition("a"), "future": definition("future")})


def test_snapshot_is_immutable_and_carries_provenance():
    snapshot = build_feature_snapshot(snapshot_id="snap-1", decision_time=ts(10), inputs=(inp("a", 4),), definitions={"a": definition("a")})
    assert snapshot.values["a"] == 1.0
    assert snapshot.provenance_for("a").source_event_ids == ("evt-a",)
    with pytest.raises(TypeError):
        snapshot.values["a"] = 2.0


def test_feature_quality_states_are_explicit():
    assert {state.value for state in FeatureQuality} == {"AVAILABLE", "MISSING", "STALE", "INVALID", "AMBIGUOUS"}


def test_rolling_window_excludes_future_and_outside_lookback_observations():
    result = build_causal_rolling_window((inp("old", 0), inp("current", 9), inp("future", 11)), decision_time=ts(10), lookback_seconds=9 * 60)
    assert [item.name for item in result] == ["current"]


def test_dependency_graph_rejects_same_time_cycles():
    with pytest.raises(FeatureLineageError, match="circular"):
        FeatureDependencyGraph({"a": ("b",), "b": ("c",), "c": ("a",)})


def test_model_state_reconstruction_uses_prior_state_only():
    assert reconstruct_model_state(((ts(1), "s1"), (ts(5), "s2"), (ts(12), "future")), decision_time=ts(10)) == "s2"


def test_model_state_reconstruction_returns_none_without_prior_state():
    assert reconstruct_model_state(((ts(11), "future"),), decision_time=ts(10)) is None


def test_naive_timestamps_are_rejected():
    with pytest.raises(FeatureLineageError, match="timezone-aware"):
        FeatureInput("a", 1.0, datetime(2026, 8, 12, 9, 0), ts(1))
