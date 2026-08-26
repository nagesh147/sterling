import pytest

from app.engines.adaptive_edge.recovery_resume import (
    RecoveryDecision,
    RecoveryError,
    RecoveryState,
    ResumeAuthorization,
    authorize_resume,
)


def recovery(**overrides):
    values = dict(
        recovery_id="recovery-1",
        source_state="halted",
        recovery_state=RecoveryState.RECOVERED,
        observation_id="obs-1",
        evidence_id="evidence-1",
        policy_id="policy-1",
        policy_version="1",
        effective_at_ms=100,
    )
    values.update(overrides)
    return RecoveryDecision(**values)


def authorization(**overrides):
    values = dict(
        resume_id="resume-1",
        recovery_id="recovery-1",
        authorized_at_ms=100,
        policy_id="policy-1",
        policy_version="1",
    )
    values.update(overrides)
    return ResumeAuthorization(**values)


def test_resume_requires_explicit_recovered_state():
    with pytest.raises(RecoveryError):
        authorize_resume(recovery(recovery_state=RecoveryState.RECOVERY_PENDING), authorization())


def test_resume_requires_matching_recovery_identity():
    with pytest.raises(RecoveryError):
        authorize_resume(recovery(), authorization(recovery_id="recovery-2"))


def test_resume_requires_matching_policy_identity():
    with pytest.raises(RecoveryError):
        authorize_resume(recovery(), authorization(policy_version="2"))


def test_resume_cannot_precede_recovery_effective_time():
    with pytest.raises(RecoveryError):
        authorize_resume(recovery(), authorization(authorized_at_ms=99))


def test_valid_resume_is_preserved():
    result = authorize_resume(recovery(), authorization())
    assert result.resume_id == "resume-1"
