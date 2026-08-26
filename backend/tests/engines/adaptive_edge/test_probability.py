import pytest

from backend.app.engines.adaptive_edge.probability import (
    HistoricalOutcome,
    Outcome,
    ProbabilityError,
    beta_binomial_posterior_mean,
    effective_sample_size,
    empirical_probability,
)


def test_equal_weight_ess_equals_raw_count():
    assert effective_sample_size([1.0, 1.0, 1.0]) == 3.0


def test_weighted_ess_is_not_raw_count():
    assert effective_sample_size([1.0, 2.0]) == pytest.approx(1.8)


def test_empirical_three_state_probability_sums_to_one():
    state = empirical_probability(
        [HistoricalOutcome(Outcome.UP), HistoricalOutcome(Outcome.UP), HistoricalOutcome(Outcome.DOWN)],
        minimum_effective_sample_size=1,
    )
    assert state.status == "OK"
    assert state.p_up == pytest.approx(2 / 3)
    assert state.p_down == pytest.approx(1 / 3)
    assert state.p_neutral == 0
    assert state.p_up + state.p_down + state.p_neutral == pytest.approx(1.0)


def test_insufficient_evidence_does_not_manufacture_probability():
    state = empirical_probability([], minimum_effective_sample_size=1)
    assert state.status == "INSUFFICIENT_DATA"
    assert state.p_up == state.p_down == state.p_neutral == 0


def test_beta_binomial_requires_explicit_prior():
    assert beta_binomial_posterior_mean(9, 1, alpha=1, beta=1) == pytest.approx(10 / 12)


def test_invalid_weights_rejected():
    with pytest.raises(ProbabilityError):
        effective_sample_size([1, 0])
