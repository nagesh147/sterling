from app.engines.adaptive_edge.target_stop import (
    TargetStopCandidate,
    select_target_stop,
)


def candidate(target: float, stop: float, conservative_ev: float) -> TargetStopCandidate:
    return TargetStopCandidate(
        target=target,
        stop=stop,
        probability_target=0.6,
        expected_gain=100.0,
        probability_stop=0.4,
        expected_loss=50.0,
        costs=5.0,
        conservative_ev=conservative_ev,
    )


def test_selects_highest_positive_conservative_ev():
    result = select_target_stop((candidate(120, 40, 12), candidate(150, 50, 18)))
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.target == 150
    assert result.candidate.conservative_ev == 18


def test_non_positive_conservative_ev_is_no_trade():
    result = select_target_stop((candidate(120, 40, 0), candidate(150, 50, -2)))
    assert result.status == "NO_TRADE"
    assert result.candidate is None


def test_empty_candidates_is_no_trade():
    result = select_target_stop(())
    assert result.status == "NO_TRADE"
    assert result.candidate is None


def test_expected_value_matches_source_relationship():
    item = candidate(120, 40, 10)
    assert item.expected_value == 35.0


def test_rejects_invalid_probability():
    item = TargetStopCandidate(
        target=100,
        stop=40,
        probability_target=1.2,
        expected_gain=100,
        probability_stop=0.2,
        expected_loss=40,
        costs=5,
        conservative_ev=1,
    )
    try:
        select_target_stop((item,))
    except ValueError as exc:
        assert "probability_target" in str(exc)
    else:
        raise AssertionError("invalid probability must be rejected")
