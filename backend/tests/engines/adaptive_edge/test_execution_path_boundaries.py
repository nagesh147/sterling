from app.engines.adaptive_edge.f113_lifecycle_boundary import evaluate_f113_boundary


def test_f113_requires_complete_prior_lifecycle_and_fresh_risk() -> None:
    assert evaluate_f113_boundary(position_is_flat=True, prior_outcome_finalized=True, new_signal_valid=True, risk_authorization_fresh=True).allowed


def test_f113_rejects_open_position() -> None:
    result = evaluate_f113_boundary(position_is_flat=False, prior_outcome_finalized=True, new_signal_valid=True, risk_authorization_fresh=True)
    assert not result.allowed
    assert result.reason == "position_not_flat"


def test_f113_rejects_stale_risk() -> None:
    result = evaluate_f113_boundary(position_is_flat=True, prior_outcome_finalized=True, new_signal_valid=True, risk_authorization_fresh=False)
    assert not result.allowed
    assert result.reason == "risk_authorization_not_fresh"
