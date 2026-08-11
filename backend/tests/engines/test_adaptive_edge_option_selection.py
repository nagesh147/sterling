from app.engines.adaptive_edge.option_selection import OptionCandidate, select_option


def test_selects_highest_positive_expected_net_ev_among_eligible_options():
    candidates = (
        OptionCandidate("NIFTY_CE_25000", 120.0, True, True, True, True),
        OptionCandidate("NIFTY_CE_25100", 180.0, True, True, True, True),
        OptionCandidate("NIFTY_CE_25200", 300.0, True, False, True, True),
    )
    result = select_option(candidates)
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.instrument == "NIFTY_CE_25100"


def test_no_trade_when_no_candidate_satisfies_validated_constraints():
    result = select_option((OptionCandidate("NIFTY_PE_25000", 100.0, True, True, False, True),))
    assert result.status == "NO_TRADE"
    assert result.candidate is None


def test_non_positive_expected_net_ev_is_ineligible():
    result = select_option((OptionCandidate("NIFTY_CE_25000", 0.0, True, True, True, True),))
    assert result.status == "NO_TRADE"
