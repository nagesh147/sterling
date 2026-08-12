import pytest

from backend.app.engines.adaptive_edge.evaluation_evidence import (
    CycleEvaluationResult,
    EvaluationEvidenceError,
    EvaluationEvidenceSet,
)


def cycle(cycle_id: str = "cycle-1", evaluation_id: str = "eval-1", **overrides) -> CycleEvaluationResult:
    values = dict(
        cycle_id=cycle_id,
        evaluation_id=evaluation_id,
        candidate_id="candidate-1",
        code_version="code-1",
        feature_version="feature-1",
        label_version="label-1",
        execution_version="execution-1",
        train_boundary_id="train-1",
        validation_boundary_id="validation-1",
        test_boundary_id="test-1",
        observation_count=10,
        independent_episode_count=8,
    )
    values.update(overrides)
    return CycleEvaluationResult(**values)


def test_evidence_set_preserves_every_cycle():
    evidence = EvaluationEvidenceSet.build((cycle("cycle-2"), cycle("cycle-1")))
    assert tuple(item.cycle_id for item in evidence.cycles) == ("cycle-2", "cycle-1")
    assert evidence.total_observations == 20
    assert evidence.total_independent_episodes == 16


def test_fingerprint_is_order_independent():
    first = EvaluationEvidenceSet.build((cycle("cycle-1"), cycle("cycle-2")))
    second = EvaluationEvidenceSet.build((cycle("cycle-2"), cycle("cycle-1")))
    assert first.fingerprint == second.fingerprint


def test_duplicate_cycle_is_rejected():
    with pytest.raises(EvaluationEvidenceError, match="duplicate cycle_id"):
        EvaluationEvidenceSet.build((cycle("cycle-1"), cycle("cycle-1")))


def test_mixed_evaluations_are_rejected():
    with pytest.raises(EvaluationEvidenceError, match="one evaluation_id"):
        EvaluationEvidenceSet.build((cycle("cycle-1", "eval-1"), cycle("cycle-2", "eval-2")))


def test_contamination_is_preserved_per_cycle():
    contaminated = cycle("cycle-2", contaminated=True, result_fingerprint="result-2")
    evidence = EvaluationEvidenceSet.build((cycle(), contaminated))
    assert evidence.contaminated_cycle_ids == ("cycle-2",)


def test_exclusions_and_episode_counts_are_preserved():
    evidence = EvaluationEvidenceSet.build((
        cycle("cycle-1", observation_count=12, independent_episode_count=9, excluded_observation_count=2),
        cycle("cycle-2", observation_count=8, independent_episode_count=6, excluded_observation_count=1),
    ))
    assert evidence.total_observations == 20
    assert evidence.total_independent_episodes == 15
    assert evidence.total_excluded_observations == 3


def test_excluded_observations_cannot_exceed_observations():
    with pytest.raises(EvaluationEvidenceError, match="cannot exceed"):
        cycle(observation_count=2, excluded_observation_count=3)
