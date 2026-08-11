from app.engines.adaptive_edge.target_stop import (
    TargetStopCandidate,
    conservative_ev_eligible,
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


def test_selects_argmax_conservative_ev():
    result = select_target_stop((candidate(120, 40, 12), candidate(150, 50, 18)))
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.target == 150
    assert result.candidate.conservative_ev == 18


def test_argmax_does_not_apply_section_34_gate():
    result = select_target_stop((candidate(120, 40, 0), candidate(150, 50, -2)))
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.conservative_ev == 0


def test_section_34_positive_gate_is_separate():
    assert conservative_ev_eligible(0.1)
    assert not conservative_ev_eligible(0.0)
    assert not conservative_ev_eligible(-0.1)


def test_empty_candidates_has_no_selection():
    result = select_target_stop(())
    assert result.status == "NO_CANDIDATE"
    assert result.candidate is None


def test_expected_value_matches_source_relationship():
    item = candidate(120, 40, 10)
    assert item.expected_value == 35.0
