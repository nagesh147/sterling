"""Explicit Bayesian-state boundary for Adaptive Edge.

The canonical specification defines Beta-state update relationships but does not
freeze initialization, decay, or learning values. This module therefore accepts
those quantities explicitly and never supplies strategy defaults.
"""
from __future__ import annotations

from dataclasses import dataclass

from .canonical_math import beta_posterior, decayed_beta


class BayesianStateError(ValueError):
    """Raised when a Bayesian-state boundary input is invalid."""


@dataclass(frozen=True)
class BetaState:
    """A Beta distribution state with explicit positive parameters."""

    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if self.alpha <= 0 or self.beta <= 0:
            raise BayesianStateError("alpha and beta must be positive")


def update_state(
    state: BetaState,
    *,
    successes: float,
    failures: float,
) -> BetaState:
    """Apply the source-defined additive Beta update."""
    if successes < 0 or failures < 0:
        raise BayesianStateError("successes and failures cannot be negative")
    alpha, beta = beta_posterior(
        state.alpha,
        state.beta,
        successes,
        failures,
    )
    return BetaState(alpha, beta)


def decayed_update_state(
    state: BetaState,
    *,
    successes: float,
    failures: float,
    rho: float,
) -> BetaState:
    """Apply the source-defined decayed Beta update with explicit ``rho``."""
    if successes < 0 or failures < 0:
        raise BayesianStateError("successes and failures cannot be negative")
    try:
        alpha, beta = decayed_beta(
            state.alpha,
            state.beta,
            successes,
            failures,
            rho,
        )
    except ValueError as exc:
        raise BayesianStateError(str(exc)) from exc
    return BetaState(alpha, beta)


def posterior_mean(state: BetaState) -> float:
    """Return the posterior mean of the Beta state."""
    return state.alpha / (state.alpha + state.beta)
