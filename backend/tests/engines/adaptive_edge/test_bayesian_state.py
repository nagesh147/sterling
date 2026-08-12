import pytest

from app.engines.adaptive_edge.bayesian_state import (
    BayesianStateError,
    BetaState,
    decayed_update_state,
    posterior_mean,
    update_state,
)


def test_additive_beta_update_preserves_source_relationship():
    state = update_state(
        BetaState(2.0, 3.0),
        successes=4.0,
        failures=1.0,
    )
    assert state == BetaState(6.0, 4.0)


def test_decayed_beta_update_requires_explicit_rho():
    state = decayed_update_state(
        BetaState(2.0, 4.0),
        successes=1.0,
        failures=2.0,
        rho=0.5,
    )
    assert state == BetaState(2.0, 4.0)


def test_posterior_mean_is_derived_from_current_state():
    assert posterior_mean(BetaState(3.0, 1.0)) == pytest.approx(0.75)


def test_initialization_does_not_accept_non_positive_parameters():
    with pytest.raises(BayesianStateError, match="positive"):
        BetaState(0.0, 1.0)


def test_observation_counts_cannot_be_negative():
    with pytest.raises(BayesianStateError, match="cannot be negative"):
        update_state(BetaState(1.0, 1.0), successes=-1.0, failures=0.0)


def test_decay_parameter_is_not_defaulted():
    with pytest.raises(TypeError):
        decayed_update_state(BetaState(1.0, 1.0), successes=1.0, failures=0.0)  # type: ignore[call-arg]


def test_decay_parameter_must_be_in_source_defined_range():
    with pytest.raises(BayesianStateError, match="rho"):
        decayed_update_state(
            BetaState(1.0, 1.0),
            successes=1.0,
            failures=0.0,
            rho=0.0,
        )
