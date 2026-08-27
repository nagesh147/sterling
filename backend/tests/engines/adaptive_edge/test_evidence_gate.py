"""The gate that lets the engine earn the right to trade.

Every offline conclusion about this strategy failed because the settling data
does not exist in any store here. This gate accumulates it live and opens only
when it clears a bar. These tests are the bar.
"""
from __future__ import annotations

import random

import pytest

from app.engines.adaptive_edge.evidence_gate import (
    MIN_OBSERVATIONS,
    MIN_SESSIONS,
    Reading,
    assess,
)


def _readings(n, *, per_session=20, credit=28.0, max_loss=28.8, mean_move=15.0, sd=12.0, seed=9):
    rng = random.Random(seed)
    return [Reading(f"d{i // per_session}", 1.2, credit, max_loss,
                    max(0.0, rng.gauss(mean_move, sd))) for i in range(n)]


# ------------------------------------------------------------- the payoff

def test_a_capped_structure_cannot_lose_more_than_its_cap():
    """That is what defined risk means. An earlier version floored the result at
    `credit - max_loss` instead of `-max_loss`, understating every capped loss
    by a whole credit and turning a losing sample profitable."""
    r = Reading("d1", 1.2, credit_bps=28.0, max_loss_bps=28.8, realised_move_bps=5_000.0)
    assert r.would_have == pytest.approx(-28.8)


def test_an_unmoved_market_keeps_the_full_credit():
    assert Reading("d1", 1.2, 28.0, 28.8, 0.0).would_have == pytest.approx(28.0)


def test_a_move_inside_the_credit_keeps_the_difference():
    assert Reading("d1", 1.2, 28.0, 28.8, 10.0).would_have == pytest.approx(28.0)
    assert Reading("d1", 1.2, 28.0, 28.8, 38.0).would_have == pytest.approx(18.0)


# --------------------------------------------------------- the three bars

def test_nothing_recorded_means_not_ready():
    verdict = assess([])
    assert verdict.ready is False
    assert "has not run" in verdict.reason


def test_too_few_observations_is_refused():
    """A left-skewed payoff flatters a small sample: the losses have not
    happened yet."""
    verdict = assess(_readings(MIN_OBSERVATIONS - 1))
    assert verdict.ready is False
    assert "observations" in verdict.reason


def test_too_few_sessions_is_refused():
    """Volatility clusters, so many readings from few days describe one regime
    rather than the strategy."""
    dense = _readings(MIN_OBSERVATIONS + 100, per_session=1_000)
    verdict = assess(dense)
    assert verdict.ready is False
    assert "sessions" in verdict.reason


def test_a_positive_mean_that_could_be_noise_is_refused():
    """The discipline that matters. The mean of a sample that could have been
    noise is not evidence."""
    noisy = _readings(MIN_OBSERVATIONS + 100, mean_move=45.0, sd=40.0)
    verdict = assess(noisy)
    assert verdict.mean_bps > 0, "this sample should have a positive mean"
    assert verdict.lower_bound_bps <= 0
    assert verdict.ready is False
    assert "could be noise" in verdict.reason


def test_a_genuinely_profitable_record_opens_the_gate():
    verdict = assess(_readings(MIN_OBSERVATIONS + 100))
    assert verdict.ready is True
    assert verdict.lower_bound_bps > 0
    assert verdict.sessions >= MIN_SESSIONS


# ---------------------------------------------------------------- reporting

def test_the_shortfall_says_what_is_still_needed():
    assert "more observations" in assess(_readings(50)).shortfall
    assert assess(_readings(MIN_OBSERVATIONS + 100)).shortfall == ""


def test_the_verdict_carries_the_measured_premium_level():
    """The median implied-to-realised ratio is the fact the whole strategy was
    missing offline, so it belongs in the verdict."""
    verdict = assess(_readings(MIN_OBSERVATIONS + 100))
    assert verdict.median_implied_ratio == pytest.approx(1.2)
    assert 0.0 <= verdict.win_rate <= 1.0


def test_the_interval_uses_sessions_not_readings():
    """Intraday readings inside one session are not independent. Counting them
    as if they were shrinks the interval by roughly the square root of
    readings-per-session and opens the gate on a regime."""
    spread = _readings(400, per_session=20)     # 20 sessions
    clustered = _readings(400, per_session=200)  # 2 sessions
    assert assess(spread).sessions == 20
    assert assess(clustered).ready is False
