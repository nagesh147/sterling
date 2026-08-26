from __future__ import annotations

from app.engines.adaptive_edge.f109_option_selection import F109Candidate
from app.engines.adaptive_edge.research_instrument_selector import ResearchInstrumentSelector


def candidate(symbol: str, ev: float) -> F109Candidate:
    return F109Candidate(
        option_symbol=symbol,
        option_type="CE",
        strike=24500,
        moneyness="ATM",
        expected_gross_ev=ev + 1,
        execution_cost=1,
        risk=100,
        liquidity=10_000,
        expected_slippage=.5,
        data_quality=1,
        required_liquidity=1_000,
        allowable_slippage=1,
        max_risk=200,
        required_data_quality=.9,
    )


def test_selector_maps_f109_candidate_to_instrument_without_execution() -> None:
    result = ResearchInstrumentSelector().select([candidate("NIFTY26AUG24500CE", 25)])
    assert result is not None
    assert result.option_symbol == "NIFTY26AUG24500CE"
    assert result.expected_net_ev == 25


def test_selector_fails_closed_when_no_candidate_is_eligible() -> None:
    result = ResearchInstrumentSelector().select([candidate("NIFTY26AUG24500CE", -1)])
    assert result is None
