"""Research-only F-105 target/stop competition and conservative EV."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import NormalDist


@dataclass(frozen=True)
class F105Candidate:
    entry_price: float
    target_price: float
    stop_price: float
    p_target: float
    p_stop: float
    p_neither: float
    neither_value: float = 0.0


@dataclass(frozen=True)
class F105EconomicAssessment:
    gross_ev: float
    execution_cost: float
    net_ev: float
    ev_standard_error: float
    conservative_ev: float
    eligible: bool
    reason: str


def evaluate_candidate(
    candidate: F105Candidate,
    *,
    execution_cost: float,
    sample_size: int,
    confidence: float = 0.95,
) -> F105EconomicAssessment:
    _validate_candidate(candidate)
    if not isfinite(execution_cost) or execution_cost < 0:
        raise ValueError("execution_cost must be finite and non-negative")
    if sample_size <= 1:
        return _blocked("insufficient_evidence")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")

    gain = candidate.target_price - candidate.entry_price
    loss = candidate.stop_price - candidate.entry_price
    gross_ev = (
        candidate.p_target * gain
        + candidate.p_stop * loss
        + candidate.p_neither * candidate.neither_value
    )
    net_ev = gross_ev - execution_cost

    # Research uncertainty proxy: finite-sample variance of the three-outcome
    # payoff distribution. Production calibration must replace/validate this
    # estimator against the authoritative statistical specification.
    outcomes = (gain, loss, candidate.neither_value)
    probabilities = (candidate.p_target, candidate.p_stop, candidate.p_neither)
    variance = sum(p * (outcome - gross_ev) ** 2 for p, outcome in zip(probabilities, outcomes))
    standard_error = (variance / sample_size) ** 0.5
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    conservative_ev = net_ev - z * standard_error

    if not isfinite(gross_ev) or not isfinite(net_ev) or not isfinite(conservative_ev):
        return _blocked("non_finite_economic_value")
    if conservative_ev <= 0:
        return F105EconomicAssessment(
            gross_ev=gross_ev,
            execution_cost=execution_cost,
            net_ev=net_ev,
            ev_standard_error=standard_error,
            conservative_ev=conservative_ev,
            eligible=False,
            reason="non_positive_conservative_ev",
        )

    return F105EconomicAssessment(
        gross_ev=gross_ev,
        execution_cost=execution_cost,
        net_ev=net_ev,
        ev_standard_error=standard_error,
        conservative_ev=conservative_ev,
        eligible=True,
        reason="eligible",
    )


def _validate_candidate(candidate: F105Candidate) -> None:
    values = (
        candidate.entry_price,
        candidate.target_price,
        candidate.stop_price,
        candidate.p_target,
        candidate.p_stop,
        candidate.p_neither,
        candidate.neither_value,
    )
    if any(not isfinite(value) for value in values):
        raise ValueError("F-105 candidate contains non-finite values")
    if candidate.target_price <= candidate.entry_price:
        raise ValueError("long-option target must be above entry")
    if candidate.stop_price >= candidate.entry_price:
        raise ValueError("long-option stop must be below entry")
    probabilities = (candidate.p_target, candidate.p_stop, candidate.p_neither)
    if any(p < 0 for p in probabilities) or abs(sum(probabilities) - 1.0) > 1e-9:
        raise ValueError("outcome probabilities must be non-negative and sum to 1")


def _blocked(reason: str) -> F105EconomicAssessment:
    return F105EconomicAssessment(
        gross_ev=0.0,
        execution_cost=0.0,
        net_ev=0.0,
        ev_standard_error=0.0,
        conservative_ev=0.0,
        eligible=False,
        reason=reason,
    )
