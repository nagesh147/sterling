from __future__ import annotations

from app.engines.adaptive_edge.f106_option_selection import (
    OptionCandidate,
    OptionSelectionPolicy,
    select_option,
)


POLICY = OptionSelectionPolicy(
    min_liquidity=100,
    max_slippage=2,
    max_risk=5000,
    min_data_quality=0.9,
)


def candidate(name: str, ev: float, *, side: str = "BUY_CE", liquidity: float = 1000) -> OptionCandidate:
    return OptionCandidate(
        instrument=name,
        side=side,
        expected_gross_ev=ev + 5,
        execution_cost=5,
        expected_net_ev=ev,
        risk=1000,
        liquidity=liquidity,
        expected_slippage=1,
        confidence=0.8,
        data_quality=1.0,
    )


def test_f106_selects_max_net_ev_not_fixed_atm() -> None:
    result = select_option((candidate("OTM1", 120), candidate("ATM", 100)), direction="BUY_CE", policy=POLICY)
    assert result.instrument == "OTM1"
    assert result.reason == "selected_max_net_ev"


def test_f106_rejects_wrong_direction_candidates() -> None:
    result = select_option((candidate("PE", 200, side="BUY_PE"),), direction="BUY_CE", policy=POLICY)
    assert result.instrument is None
    assert result.reason == "no_eligible_instrument"


def test_f106_applies_liquidity_constraint() -> None:
    result = select_option((candidate("LOW_LIQ", 200, liquidity=10), candidate("GOOD", 100)), direction="BUY_CE", policy=POLICY)
    assert result.instrument == "GOOD"


def test_f106_no_direction_means_no_selection() -> None:
    result = select_option((candidate("ATM", 200),), direction="NO_TRADE", policy=POLICY)
    assert result.instrument is None
    assert result.reason == "no_directional_entry"
