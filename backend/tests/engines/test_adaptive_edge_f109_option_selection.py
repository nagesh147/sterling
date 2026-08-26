from app.engines.adaptive_edge.f109_option_selection import F109Candidate, select_f109


def candidate(symbol: str, ev: float, *, risk: float = 100, liq: float = 100, slip: float = 1, quality: float = 1) -> F109Candidate:
    return F109Candidate(
        option_symbol=symbol,
        option_type="CE",
        strike=24500,
        moneyness="ATM",
        expected_gross_ev=ev + 2,
        execution_cost=2,
        risk=risk,
        liquidity=liq,
        expected_slippage=slip,
        data_quality=quality,
        required_liquidity=50,
        allowable_slippage=2,
        max_risk=100,
        required_data_quality=0.8,
    )


def test_f109_selects_highest_positive_net_ev_not_atm_by_default() -> None:
    atm = candidate("ATM", 10)
    otm = candidate("OTM1", 20)
    assert select_f109([atm, otm]) is otm


def test_f109_rejects_candidate_above_risk_limit() -> None:
    assert select_f109([candidate("ATM", 20, risk=101)]) is None


def test_f109_rejects_candidate_below_liquidity_requirement() -> None:
    assert select_f109([candidate("ATM", 20, liq=49)]) is None


def test_f109_rejects_candidate_above_slippage_limit() -> None:
    assert select_f109([candidate("ATM", 20, slip=2.01)]) is None


def test_f109_rejects_missing_economic_inputs() -> None:
    c = candidate("ATM", 20)
    c = F109Candidate(**{**c.__dict__, "expected_gross_ev": None})
    assert select_f109([c]) is None


def test_f109_is_deterministic_on_equal_net_ev() -> None:
    a = candidate("NIFTY24500CE", 20)
    b = candidate("NIFTY24600CE", 20)
    assert select_f109([b, a]) is b
    assert select_f109([a, b]) is b
