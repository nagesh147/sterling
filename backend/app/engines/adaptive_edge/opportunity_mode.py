"""Opportunity horizon mode: MICRO / SCALP / EXTENDED_SCALP / INTRADAY.

Canonical states from LIVE POSITION STATE TRANSITION §20–31.
Numeric cutoffs are caller-supplied ModePolicy, not recovered F-104.
Elapsed time alone cannot change mode. Price alone cannot change mode.
Mode cannot change authorized risk or loosen protection.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .lifecycle_engine import HorizonState


class OpportunityMode(str, Enum):
    MICRO = "MICRO"
    SCALP = "SCALP"
    EXTENDED_SCALP = "EXTENDED_SCALP"
    INTRADAY = "INTRADAY"


MODE_ORDER: tuple[OpportunityMode, ...] = (
    OpportunityMode.MICRO,
    OpportunityMode.SCALP,
    OpportunityMode.EXTENDED_SCALP,
    OpportunityMode.INTRADAY,
)

MODE_TO_HORIZON: dict[OpportunityMode, HorizonState] = {
    OpportunityMode.MICRO: HorizonState.IMPULSE,
    OpportunityMode.SCALP: HorizonState.TACTICAL,
    OpportunityMode.EXTENDED_SCALP: HorizonState.INTRADAY_SWING,
    OpportunityMode.INTRADAY: HorizonState.SESSION_TREND,
}

HORIZON_TO_MODE: dict[HorizonState, OpportunityMode] = {
    HorizonState.IMPULSE: OpportunityMode.MICRO,
    HorizonState.TACTICAL: OpportunityMode.SCALP,
    HorizonState.INTRADAY_SWING: OpportunityMode.EXTENDED_SCALP,
    HorizonState.SESSION_TREND: OpportunityMode.INTRADAY,
    HorizonState.SESSION_EXTENSION: OpportunityMode.INTRADAY,
}

ALLOWED_EDGES: frozenset[tuple[OpportunityMode, OpportunityMode]] = frozenset(
    {
        (OpportunityMode.MICRO, OpportunityMode.SCALP),
        (OpportunityMode.SCALP, OpportunityMode.MICRO),
        (OpportunityMode.SCALP, OpportunityMode.EXTENDED_SCALP),
        (OpportunityMode.EXTENDED_SCALP, OpportunityMode.SCALP),
        (OpportunityMode.EXTENDED_SCALP, OpportunityMode.INTRADAY),
        (OpportunityMode.INTRADAY, OpportunityMode.EXTENDED_SCALP),
        (OpportunityMode.MICRO, OpportunityMode.EXTENDED_SCALP),
        (OpportunityMode.EXTENDED_SCALP, OpportunityMode.MICRO),
        (OpportunityMode.MICRO, OpportunityMode.INTRADAY),
        (OpportunityMode.INTRADAY, OpportunityMode.MICRO),
        (OpportunityMode.SCALP, OpportunityMode.INTRADAY),
        (OpportunityMode.INTRADAY, OpportunityMode.SCALP),
    }
)


@dataclass(frozen=True)
class ModePolicy:
    """Explicit research/production policy. Not a learned F-104 freeze."""

    label: str
    persistence_bars: int = 3
    scalp_favorable_points: float = 5.0
    extended_favorable_points: float = 15.0
    intraday_favorable_points: float = 25.0
    max_giveback_ratio: float = 0.6
    intraday_min_minutes_remaining: float = 45.0

    def __post_init__(self) -> None:
        if self.persistence_bars < 1:
            raise ValueError("persistence_bars must be >= 1")
        if not (
            0
            < self.scalp_favorable_points
            <= self.extended_favorable_points
            <= self.intraday_favorable_points
        ):
            raise ValueError("favorable ladders must be positive and non-decreasing")
        if not 0 < self.max_giveback_ratio <= 1:
            raise ValueError("max_giveback_ratio must be in (0, 1]")


@dataclass(frozen=True)
class ModeEvidence:
    score_aligned: bool
    features_valid: bool
    data_certain: bool
    favorable_points: float
    giveback_ratio: float
    minutes_to_cutoff: float
    holding_age_seconds: float
    probability_note: str = "not_F102"
    continuation_note: str = "favorable_and_giveback_policy"
    economic_note: str = "giveback_ratio_policy"


@dataclass(frozen=True)
class ModeTransitionRecord:
    previous_mode: OpportunityMode
    new_mode: OpportunityMode
    timestamp: str
    trigger_reason: str
    favorable_points: float
    giveback_ratio: float
    holding_age_seconds: float
    minutes_to_cutoff: float
    persistence_bars: int
    model_version: str = "research-mode-1"


@dataclass(frozen=True)
class ModeDecision:
    mode: OpportunityMode
    candidate: OpportunityMode
    transitioned: bool
    promoted: bool
    downgraded: bool
    horizon: HorizonState
    reason: str
    persistence_count: int


def research_mode_policy() -> ModePolicy:
    return ModePolicy(label="RESEARCH_NOT_LIVE_EXPLICIT_MODE_POLICY")


def _rank(mode: OpportunityMode) -> int:
    return MODE_ORDER.index(mode)


def propose_mode(evidence: ModeEvidence, policy: ModePolicy) -> OpportunityMode:
    """Conjunction of recovered observables. No single-variable promotion."""
    if not (evidence.score_aligned and evidence.features_valid and evidence.data_certain):
        return OpportunityMode.MICRO
    if evidence.giveback_ratio > policy.max_giveback_ratio:
        return OpportunityMode.MICRO
    favorable = evidence.favorable_points
    if (
        favorable >= policy.intraday_favorable_points
        and evidence.minutes_to_cutoff >= policy.intraday_min_minutes_remaining
    ):
        return OpportunityMode.INTRADAY
    if favorable >= policy.extended_favorable_points:
        return OpportunityMode.EXTENDED_SCALP
    if favorable >= policy.scalp_favorable_points:
        return OpportunityMode.SCALP
    return OpportunityMode.MICRO


class OpportunityModeEngine:
    def __init__(self, policy: ModePolicy, *, started_at: str) -> None:
        self.policy = policy
        self.mode = OpportunityMode.MICRO
        self.started_at = started_at
        self._candidate = OpportunityMode.MICRO
        self._streak = 0
        self.records: list[ModeTransitionRecord] = []

    def update(self, evidence: ModeEvidence, *, timestamp: str) -> ModeDecision:
        candidate = propose_mode(evidence, self.policy)
        if candidate is self._candidate:
            self._streak += 1
        else:
            self._candidate = candidate
            self._streak = 1

        reason = "hold"
        transitioned = False
        if (
            candidate is not self.mode
            and self._streak >= self.policy.persistence_bars
            and (self.mode, candidate) in ALLOWED_EDGES
        ):
            previous = self.mode
            self.mode = candidate
            transitioned = True
            reason = f"{previous.value}->{candidate.value}"
            self.records.append(
                ModeTransitionRecord(
                    previous_mode=previous,
                    new_mode=candidate,
                    timestamp=timestamp,
                    trigger_reason=reason,
                    favorable_points=evidence.favorable_points,
                    giveback_ratio=evidence.giveback_ratio,
                    holding_age_seconds=evidence.holding_age_seconds,
                    minutes_to_cutoff=evidence.minutes_to_cutoff,
                    persistence_bars=self._streak,
                )
            )
        elif candidate is not self.mode:
            reason = f"hysteresis_{self._streak}/{self.policy.persistence_bars}"

        promoted = transitioned and _rank(self.mode) > _rank(
            self.records[-1].previous_mode if transitioned else self.mode
        )
        downgraded = transitioned and not promoted
        if transitioned:
            previous = self.records[-1].previous_mode
            promoted = _rank(self.mode) > _rank(previous)
            downgraded = _rank(self.mode) < _rank(previous)
        return ModeDecision(
            mode=self.mode,
            candidate=candidate,
            transitioned=transitioned,
            promoted=promoted,
            downgraded=downgraded,
            horizon=MODE_TO_HORIZON[self.mode],
            reason=reason,
            persistence_count=self._streak,
        )
