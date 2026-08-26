from app.engines.adaptive_edge.option_selection import OptionCandidate, select_option


def test_selects_highest_expected_net_ev_among_constraint_eligible_options():
    candidates = (
        OptionCandidate("NIFTY_CE_25000", 120.0, True, True, True, True),
        OptionCandidate("NIFTY_CE_25100", 180.0, True, True, True, True),
        OptionCandidate("NIFTY_CE_25200", 300.0, True, False, True, True),
    )
    result = select_option(candidates)
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.instrument == "NIFTY_CE_25100"


def test_no_candidate_when_no_option_satisfies_validated_constraints():
    result = select_option((OptionCandidate("NIFTY_PE_25000", 100.0, True, True, False, True),))
    assert result.status == "NO_CANDIDATE"
    assert result.candidate is None


def test_selection_does_not_apply_the_downstream_positive_ev_gate():
    result = select_option((OptionCandidate("NIFTY_CE_25000", -10.0, True, True, True, True),))
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.expected_net_ev == -10.0
