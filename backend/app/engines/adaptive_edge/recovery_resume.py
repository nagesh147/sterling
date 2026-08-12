"""A57 recovery/resume primitives.

Recovery is explicit and evidence-backed; clearing an incident never silently
restores trading permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryError(ValueError):
    """Raised when a recovery/resume invariant is violated."""


class RecoveryState(str, Enum):
    RECOVERY_PENDING = "recovery_pending"
    RECOVERED = "recovered"


@dataclass(frozen=True)
class RecoveryDecision:
    recovery_id: str
    source_state: str
    recovery_state: RecoveryState
    observation_id: str
    evidence_id: str
    policy_id: str
    policy_version: str
    effective_at_ms: int

    def __post_init__(self) -> None:
        for value, name in (
            (self.recovery_id, "recovery_id"),
            (self.source_state, "source_state"),
            (self.observation_id, "observation_id"),
            (self.evidence_id, "evidence_id"),
            (self.policy_id, "policy_id"),
            (self.policy_version, "policy_version"),
        ):
            if not value.strip():
                raise RecoveryError(f"{name} must not be empty")
        if self.effective_at_ms < 0:
            raise RecoveryError("effective_at_ms must be non-negative")


@dataclass(frozen=True)
class ResumeAuthorization:
    resume_id: str
    recovery_id: str
    authorized_at_ms: int
    policy_id: str
    policy_version: str

    def __post_init__(self) -> None:
        for value, name in (
            (self.resume_id, "resume_id"),
            (self.recovery_id, "recovery_id"),
            (self.policy_id, "policy_id"),
            (self.policy_version, "policy_version"),
        ):
            if not value.strip():
                raise RecoveryError(f"{name} must not be empty")
        if self.authorized_at_ms < 0:
            raise RecoveryError("authorized_at_ms must be non-negative")


def authorize_resume(recovery: RecoveryDecision, authorization: ResumeAuthorization) -> ResumeAuthorization:
    if recovery.recovery_state is not RecoveryState.RECOVERED:
        raise RecoveryError("resume requires recovered state")
    if authorization.recovery_id != recovery.recovery_id:
        raise RecoveryError("resume must reference the recovery decision")
    if authorization.policy_id != recovery.policy_id or authorization.policy_version != recovery.policy_version:
        raise RecoveryError("resume policy identity must match recovery policy")
    if authorization.authorized_at_ms < recovery.effective_at_ms:
        raise RecoveryError("resume authorization cannot precede recovery effectiveness")
    return authorization
