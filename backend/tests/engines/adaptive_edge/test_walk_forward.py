from datetime import datetime

import pytest

from app.engines.adaptive_edge.walk_forward import (
    CandidateResult,
    CandidateSpec,
    EvaluationContractError,
    EvaluationCycle,
    EvaluationObservation,
    FinalHoldout,
    HoldoutStatus,
    ObservationDisposition,
    ResearchRegistry,
    TemporalSpan,
    TestSetContaminatedError,
    TestUseEvent,
    assign_observation,
    count_independent_episodes,
    detect_overlapping_outcomes,
    eligible_training_observations,
    final_test_is_claim_eligible,
    purge_for_boundary,
    validate_walk_forward_sequence,
)


def dt(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 1, day, hour, 0, 0)


def cycle() -> EvaluationCycle:
    return EvaluationCycle(
        cycle_id="c1",
        training=TemporalSpan(dt(1), dt(10)),
        validation=TemporalSpan(dt(10), dt(13)),
        test=TemporalSpan(dt(13), dt(16)),
        promotion_time=dt(12, 23),
        feature_policy_version="features-v1",
        label_policy_version="labels-vUNKNOWN",
        model_policy_version="model-v1",
    )


def observation(
    observation_id: str,
    decision_day: int,
    *,
    feature_day: int | None = None,
    maturity_day: int | None = None,
    outcome: tuple[int, int] | None = None,
    episode: str | None = None,
) -> EvaluationObservation:
    return EvaluationObservation(
        observation_id=observation_id,
        decision_time=dt(decision_day),
        feature_available_time=dt(feature_day if feature_day is not None else decision_day),
        label_maturity_time=dt(maturity_day) if maturity_day is not None else None,
        outcome_span=(TemporalSpan(dt(outcome[0]), dt(outcome[1])) if outcome else None),
        independent_episode_id=episode,
    )


def test_training_requires_causal_features_and_mature_labels() -> None:
    c = cycle()
    rows = [
        observation("ok", 5, maturity_day=9),
        observation("future-feature", 5, feature_day=6, maturity_day=9),
        observation("immature", 5, maturity_day=10),
        observation("outside", 12, maturity_day=12),
    ]

    assert [row.observation_id for row in eligible_training_observations(rows, c)] == ["ok"]
    assert assign_observation(rows[0], c) is ObservationDisposition.TRAIN
    assert assign_observation(rows[1], c) is ObservationDisposition.INELIGIBLE


def test_cycle_rejects_overlapping_windows_and_late_promotion() -> None:
    with pytest.raises(EvaluationContractError, match="training and validation"):
        EvaluationCycle(
            cycle_id="bad",
            training=TemporalSpan(dt(1), dt(11)),
            validation=TemporalSpan(dt(10), dt(13)),
            test=TemporalSpan(dt(13), dt(16)),
        )

    with pytest.raises(EvaluationContractError, match="before test"):
        EvaluationCycle(
            cycle_id="bad",
            training=TemporalSpan(dt(1), dt(10)),
            validation=TemporalSpan(dt(10), dt(13)),
            test=TemporalSpan(dt(13), dt(16)),
            promotion_time=dt(14),
        )


def test_walk_forward_test_boundaries_must_advance() -> None:
    c1 = cycle()
    c2 = EvaluationCycle(
        cycle_id="c2",
        training=TemporalSpan(dt(1), dt(13)),
        validation=TemporalSpan(dt(13), dt(16)),
        test=TemporalSpan(dt(16), dt(19)),
        promotion_time=dt(15, 23),
    )
    validate_walk_forward_sequence([c1, c2])

    with pytest.raises(EvaluationContractError, match="test boundaries"):
        validate_walk_forward_sequence([c2, c1])


def test_purge_uses_resolved_outcome_spans_and_never_invents_a_horizon() -> None:
    rows = [
        observation("crossing", 5, maturity_day=9, outcome=(9, 11)),
        observation("safe", 5, maturity_day=9, outcome=(7, 9)),
        observation("unknown-horizon", 5, maturity_day=9),
    ]
    safe, purged = purge_for_boundary(rows, TemporalSpan(dt(10), dt(13)))

    assert [row.observation_id for row in purged] == ["crossing"]
    assert {row.observation_id for row in safe} == {"safe", "unknown-horizon"}


def test_overlapping_outcomes_are_detected_without_assuming_iid() -> None:
    rows = [
        observation("a", 3, maturity_day=8, outcome=(4, 8), episode="e1"),
        observation("b", 4, maturity_day=9, outcome=(7, 10), episode="e1"),
        observation("c", 5, maturity_day=9, outcome=(11, 12), episode="e2"),
    ]

    assert detect_overlapping_outcomes(rows) == [("a", "b")]
    assert count_independent_episodes(rows) == 2


def test_registry_preserves_all_candidates_and_results() -> None:
    registry = ResearchRegistry()
    candidate = CandidateSpec(
        candidate_id="candidate-1",
        code_version="abc123",
        feature_version="features-v1",
        label_version="labels-vUNKNOWN",
        parameter_set=(("x", "1"),),
        execution_model_version="execution-UNKNOWN",
        selection_rationale="validation-selected",
    )
    registry.register_candidate(candidate)
    registry.record_result(CandidateResult("candidate-1", "c1", (("metric", 1.0),)))

    assert list(registry.candidates) == ["candidate-1"]
    assert len(registry.results) == 1


def test_final_holdout_cannot_be_used_before_freeze_or_to_tune() -> None:
    registry = ResearchRegistry()
    candidate = CandidateSpec("candidate-1", "abc", "f1", "l1")
    registry.register_candidate(candidate)
    holdout = FinalHoldout()

    with pytest.raises(EvaluationContractError, match="before selection"):
        holdout.record_use(influenced_selection=False)

    holdout.freeze("candidate-1", dt(20))
    holdout.record_use(influenced_selection=False)
    assert holdout.status is HoldoutStatus.FROZEN
    assert final_test_is_claim_eligible(registry, holdout)

    with pytest.raises(TestSetContaminatedError):
        holdout.record_use(influenced_selection=True)
    assert holdout.status is HoldoutStatus.CONTAMINATED
    assert not final_test_is_claim_eligible(registry, holdout)


def test_registry_marks_test_use_that_influenced_selection_as_contamination() -> None:
    registry = ResearchRegistry()
    registry.register_candidate(CandidateSpec("candidate-1", "abc", "f1", "l1"))
    registry.record_test_use(TestUseEvent("candidate-1", "c1", "tuning", True))
    assert registry.test_contaminated


def test_final_test_claim_requires_frozen_holdout_and_clean_registry() -> None:
    registry = ResearchRegistry()
    registry.register_candidate(CandidateSpec("candidate-1", "abc", "f1", "l1"))
    holdout = FinalHoldout()
    assert not final_test_is_claim_eligible(registry, holdout)

    holdout.freeze("candidate-1", dt(20))
    assert final_test_is_claim_eligible(registry, holdout)
