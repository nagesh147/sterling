import pytest

from app.engines.adaptive_edge.option_selection import (
    OptionCandidate,
    select_option,
)


def candidate(instrument: str, ev: float, **overrides: bool) -> OptionCandidate:
    flags = {
        "liquidity_ok": True,
        "slippage_ok": True,
        "risk_ok": True,
        "data_quality_ok": True,
    }
    flags.update(overrides)
    return OptionCandidate(instrument, ev, **flags)


def test_selects_maximum_expected_net_ev_among_valid_candidates():
    result = select_option(
        [candidate("NIFTY-CE-1", 10.0), candidate("NIFTY-CE-2", 15.0)]
    )
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.instrument == "NIFTY-CE-2"


def test_invalid_candidate_is_excluded_before_argmax():
    result = select_option(
        [
            candidate("INVALID", 100.0, risk_ok=False),
            candidate("VALID", 10.0),
        ]
    )
    assert result.status == "SELECTED"
    assert result.candidate is not None
    assert result.candidate.instrument == "VALID"


@pytest.mark.parametrize(
    "flag",
    ["liquidity_ok", "slippage_ok", "risk_ok", "data_quality_ok"],
)
def test_each_validation_constraint_is_required(flag: str):
    result = select_option([candidate("REJECTED", 100.0, **{flag: False})])
    assert result.status == "NO_CANDIDATE"
    assert result.candidate is None


def test_empty_candidate_set_is_not_an_error():
    result = select_option([])
    assert result.status == "NO_CANDIDATE"
    assert result.candidate is None
