"""Let the engine earn the right to trade, from its own live readings.

Every offline conclusion about this strategy failed for the same reason: the
data to settle it does not exist in any store here. The directional model had no
edge. The long-volatility gate reduced to needing implied below realised, which
index options rarely offer. The short-volatility study measured a payoff that is
mostly not listed. What was missing each time was option prices.

The engine has them, live. So rather than ship a threshold argued from history,
it ships a gate that accumulates its own evidence and opens only when that
evidence clears a bar — and stays shut until then, without anyone having to
remember to keep it shut.

The bar is deliberately a lower confidence bound rather than a mean. A strategy
that is profitable on average across a sample that could equally have been noise
is not one to put money behind, and the mean cannot tell those apart.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Sequence

#: Readings before the gate will consider opening. A short-volatility payoff is
#: heavily left-skewed, so a small sample is systematically flattering: the
#: losses simply have not happened yet.
MIN_OBSERVATIONS = 400

#: Distinct sessions those readings must span. 400 observations from three days
#: is three days of one regime, and volatility regimes persist for weeks.
MIN_SESSIONS = 20

#: Confidence for the lower bound. Two-sided 95%.
CONFIDENCE_Z = 1.96


@dataclass(frozen=True)
class Reading:
    """One decision the engine made, and what happened after it.

    `would_have` is the outcome of the structure the engine priced, not of a
    trade it placed. That is the point: the gate learns from decisions it
    declined to act on, which is the only way to gather evidence before trading.
    """

    session: str
    implied_ratio: float
    credit_bps: float
    max_loss_bps: float
    realised_move_bps: float

    @property
    def would_have(self) -> float:
        """P&L of a defined-risk short structure, in basis points.

        Floored at `-max_loss_bps`, which is what "defined risk" means. An
        earlier version returned `credit - min(loss, max_loss)`, flooring the
        result at `credit - max_loss` instead — understating every capped loss
        by a whole credit and making a losing sample read as profitable. It is
        the same shape of error as pricing a condor without paying for its wings.
        """
        loss = max(0.0, self.realised_move_bps - self.credit_bps)
        return max(-self.max_loss_bps, self.credit_bps - loss)


@dataclass(frozen=True)
class Verdict:
    """Whether the accumulated evidence supports trading, and what it shows."""

    ready: bool
    observations: int
    sessions: int
    mean_bps: float
    lower_bound_bps: float
    median_implied_ratio: float
    win_rate: float
    reason: str

    @property
    def shortfall(self) -> str:
        if self.observations < MIN_OBSERVATIONS:
            return f"{MIN_OBSERVATIONS - self.observations} more observations"
        if self.sessions < MIN_SESSIONS:
            return f"{MIN_SESSIONS - self.sessions} more sessions"
        return ""


def assess(readings: Sequence[Reading]) -> Verdict:
    """Does the live record support arming the strategy?

    Three things must hold, and each is there because a specific way of being
    wrong was already met while building this engine:

    * **Enough observations.** A left-skewed payoff flatters a small sample.
    * **Enough distinct sessions.** Volatility clusters, so many readings from
      few days describe one regime rather than the strategy.
    * **A positive lower bound, not a positive mean.** The mean of a sample that
      could have been noise is not evidence.
    """
    n = len(readings)
    if n == 0:
        return Verdict(False, 0, 0, 0.0, 0.0, 0.0, 0.0,
                       "no readings yet — the engine has not run")

    sessions = len({r.session for r in readings})
    pnl = [r.would_have for r in readings]
    mean = statistics.mean(pnl)
    ratios = sorted(r.implied_ratio for r in readings)
    median_ratio = ratios[len(ratios) // 2]
    wins = sum(1 for x in pnl if x > 0) / n

    # Standard error on the mean, using the session count rather than the
    # observation count when readings are clustered inside sessions — intraday
    # readings are not independent, and pretending they are shrinks the interval
    # by roughly the square root of readings-per-session.
    spread = statistics.pstdev(pnl) if n > 1 else 0.0
    effective_n = max(1, sessions)
    lower = mean - CONFIDENCE_Z * (spread / math.sqrt(effective_n)) if spread > 0 else mean

    if n < MIN_OBSERVATIONS:
        return Verdict(False, n, sessions, mean, lower, median_ratio, wins,
                       f"{n} of {MIN_OBSERVATIONS} observations — a left-skewed payoff "
                       f"flatters a small sample")
    if sessions < MIN_SESSIONS:
        return Verdict(False, n, sessions, mean, lower, median_ratio, wins,
                       f"{sessions} of {MIN_SESSIONS} sessions — volatility clusters, so "
                       f"these readings may describe one regime")
    if lower <= 0:
        return Verdict(False, n, sessions, mean, lower, median_ratio, wins,
                       f"95% lower bound {lower:+.2f}bps is not positive — the mean of "
                       f"{mean:+.2f} could be noise")

    return Verdict(True, n, sessions, mean, lower, median_ratio, wins,
                   f"{n} readings over {sessions} sessions, 95% lower bound "
                   f"{lower:+.2f}bps at a median implied/realised of {median_ratio:.2f}")
