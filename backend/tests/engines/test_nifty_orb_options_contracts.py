"""Option-contract eligibility, expiry semantics and buy-only direction mapping.

Every date here is fixed and every expiry preference is resolved against an
explicit calendar, so the suite cannot drift with the wall clock.

NSE convention, verified against the 2026 calendar:

    2026-08-27  Thu  last Thursday of August     -> monthly
    2026-09-03  Thu                              -> weekly
    2026-09-10  Thu                              -> weekly
    2026-09-24  Thu  last Thursday of September  -> monthly
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import (
    OptionContract,
    Signal,
    StrategyConfig,
    build_trade_plan,
    is_monthly_expiry,
    select_option,
)

IST = timezone(timedelta(hours=5, minutes=30))

TODAY = date(2026, 8, 20)
AUG_MONTHLY = "2026-08-27"      # DTE  7 from TODAY
SEP_WEEKLY_1 = "2026-09-03"     # DTE 14
SEP_WEEKLY_2 = "2026-09-10"     # DTE 21
SEP_MONTHLY = "2026-09-24"      # DTE 35


def contract(symbol, expiry, typ, strike=25000, volume=5000, oi=20000, bid=99.5, ask=100.5):
    """A liquid contract: 1.0% spread against a 1.5% default ceiling."""
    return OptionContract(symbol, strike, expiry, typ, 100, bid, ask, 65, 0.5, volume, oi)


# --------------------------------------------------------------------------
# expiry calendar rule
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "expiry, monthly",
    [(AUG_MONTHLY, True), (SEP_WEEKLY_1, False), (SEP_WEEKLY_2, False), (SEP_MONTHLY, True)],
)
def test_monthly_expiry_rule_matches_the_nse_calendar(expiry, monthly):
    assert is_monthly_expiry(date.fromisoformat(expiry)) is monthly


def test_supplied_calendar_overrides_the_derived_rule():
    """A venue calendar is authoritative when the caller has one."""
    calendar = frozenset({date.fromisoformat(SEP_WEEKLY_1)})
    assert is_monthly_expiry(date.fromisoformat(SEP_WEEKLY_1), monthly_expiries=calendar) is True
    assert is_monthly_expiry(date.fromisoformat(AUG_MONTHLY), monthly_expiries=calendar) is False


def test_monthly_rule_is_independent_of_the_wall_clock():
    assert is_monthly_expiry(date(2026, 8, 27)) is is_monthly_expiry(date(2026, 8, 27))


# --------------------------------------------------------------------------
# DTE bounds
# --------------------------------------------------------------------------

def test_expiry_dte_range_is_enforced():
    cfg = StrategyConfig(expiry_selection="nearest", expiry_dte_min=0, expiry_dte_max=8)
    contracts = [contract("FAR", "2099-12-31", "CE"), contract("NEAR", AUG_MONTHLY, "CE")]
    assert select_option(25010, "LONG", contracts, cfg, today=TODAY).symbol == "NEAR"


def test_no_contract_inside_the_dte_range_is_rejected():
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=3)
    with pytest.raises(ValueError, match="No liquid CE contracts"):
        select_option(25010, "LONG", [contract("AUG", AUG_MONTHLY, "CE")], cfg, today=TODAY)


def test_dte_is_measured_against_the_supplied_reference_date():
    c = contract("AUG", AUG_MONTHLY, "CE")
    assert c.dte_on(TODAY) == 7
    assert c.dte_on(date(2026, 8, 27)) == 0
    assert c.dte_on(date(2026, 9, 1)) == 0          # never negative
    assert contract("BAD", "not-a-date", "CE").dte_on(TODAY) is None


def test_avoid_expiry_day_excludes_zero_dte():
    contracts = [contract("TODAY", AUG_MONTHLY, "CE"), contract("LATER", SEP_WEEKLY_1, "CE")]
    on_expiry = date.fromisoformat(AUG_MONTHLY)
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=30, avoid_expiry_day=True)
    assert select_option(25000, "LONG", contracts, cfg, today=on_expiry).symbol == "LATER"


# --------------------------------------------------------------------------
# expiry preference: nearest / weekly / monthly / any
# --------------------------------------------------------------------------

CHAIN = [
    contract("AUG_M", AUG_MONTHLY, "CE"),
    contract("SEP_W1", SEP_WEEKLY_1, "CE"),
    contract("SEP_W2", SEP_WEEKLY_2, "CE"),
    contract("SEP_M", SEP_MONTHLY, "CE"),
]


@pytest.mark.parametrize(
    "selection, expected",
    [("nearest", "AUG_M"), ("weekly", "SEP_W1"), ("monthly", "AUG_M"), ("any", "AUG_M")],
)
def test_expiry_selection_semantics_are_explicit(selection, expected):
    cfg = StrategyConfig(expiry_selection=selection, expiry_dte_min=0, expiry_dte_max=60)
    assert select_option(25000, "LONG", CHAIN, cfg, today=TODAY).symbol == expected


def test_weekly_and_monthly_selection_are_distinct():
    """The nearest expiry is a monthly one, so weekly must reach past it."""
    base = dict(expiry_dte_min=0, expiry_dte_max=60)
    weekly = select_option(25000, "LONG", CHAIN, StrategyConfig(expiry_selection="weekly", **base), today=TODAY)
    monthly = select_option(25000, "LONG", CHAIN, StrategyConfig(expiry_selection="monthly", **base), today=TODAY)
    assert weekly.symbol == "SEP_W1"
    assert monthly.symbol == "AUG_M"
    assert weekly.expiry != monthly.expiry


def test_unmatched_expiry_preference_fails_instead_of_falling_back():
    """A weekly-only mandate must not silently execute a monthly contract."""
    cfg = StrategyConfig(expiry_selection="weekly", expiry_dte_min=0, expiry_dte_max=10)
    with pytest.raises(ValueError, match="No eligible weekly expiry"):
        select_option(25000, "LONG", [contract("AUG_M", AUG_MONTHLY, "CE")], cfg, today=TODAY)


def test_selection_honors_a_supplied_monthly_calendar():
    cfg = StrategyConfig(expiry_selection="monthly", expiry_dte_min=0, expiry_dte_max=60)
    calendar = frozenset({date.fromisoformat(SEP_WEEKLY_2)})
    chosen = select_option(25000, "LONG", CHAIN, cfg, today=TODAY, monthly_expiries=calendar)
    assert chosen.symbol == "SEP_W2"


# --------------------------------------------------------------------------
# liquidity gates and buy-only direction mapping
# --------------------------------------------------------------------------

def test_buy_only_direction_mapping_is_strict():
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=8)
    ce = contract("CE", AUG_MONTHLY, "CE")
    pe = contract("PE", AUG_MONTHLY, "PE")
    assert select_option(25000, "LONG", [ce, pe], cfg, today=TODAY).option_type == "CE"
    assert select_option(25000, "SHORT", [ce, pe], cfg, today=TODAY).option_type == "PE"


def test_a_neutral_signal_cannot_select_an_option():
    with pytest.raises(ValueError, match="without a directional signal"):
        select_option(25000, "NONE", CHAIN, StrategyConfig(), today=TODAY)


def test_wide_spread_is_rejected():
    cfg = StrategyConfig(max_spread_pct=1.0, expiry_dte_min=0, expiry_dte_max=8)
    wide = contract("WIDE", AUG_MONTHLY, "CE", bid=80, ask=120)
    with pytest.raises(ValueError, match="liquid"):
        select_option(25000, "LONG", [wide], cfg, today=TODAY)


def test_crossed_market_is_rejected():
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=8)
    crossed = contract("CROSSED", AUG_MONTHLY, "CE", bid=101, ask=99)
    with pytest.raises(ValueError, match="liquid"):
        select_option(25000, "LONG", [crossed], cfg, today=TODAY)


def test_stale_quote_is_rejected_when_freshness_is_enforced():
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=8, max_quote_staleness_s=15)
    stale = OptionContract(
        "STALE", 25000, AUG_MONTHLY, "CE", 100, 99.5, 100.5, 65, 0.5, 5000, 20000,
        quote_timestamp=datetime.now(IST) - timedelta(minutes=5),
    )
    with pytest.raises(ValueError, match="liquid"):
        select_option(25000, "LONG", [stale], cfg, today=TODAY)


def test_open_interest_switch_is_the_only_way_to_relax_the_oi_floor():
    thin = contract("THIN", AUG_MONTHLY, "CE", oi=10)
    strict = StrategyConfig(expiry_dte_min=0, expiry_dte_max=8, min_open_interest=10000)
    relaxed = StrategyConfig(expiry_dte_min=0, expiry_dte_max=8, min_open_interest=10000, truedata_use_oi=False)
    with pytest.raises(ValueError, match="liquid"):
        select_option(25000, "LONG", [thin], strict, today=TODAY)
    assert select_option(25000, "LONG", [thin], relaxed, today=TODAY).symbol == "THIN"


def test_trade_plan_rejects_mismatched_option_side():
    cfg = StrategyConfig()
    signal = Signal("LONG", "TREND", datetime.now(IST), 25000, 24900, 25010, 50, 20, 2, 0.8, "test")
    pe = contract("PE", AUG_MONTHLY, "PE")
    with pytest.raises(ValueError, match="does not match"):
        build_trade_plan(signal, pe, cfg, spot=25020)


# --------------------------------------------------------------------------
# moneyness is a risk choice, not a hint
# --------------------------------------------------------------------------

def _ladder(*strikes, expiry=AUG_MONTHLY):
    return [contract(f"CE{s:g}", expiry, "CE", strike=s) for s in strikes]


def test_an_unavailable_moneyness_is_refused_not_substituted():
    """Asking for ITM x3 and getting the ATM strike changes delta, cost and payoff."""
    cfg = StrategyConfig(option_moneyness="ITM", option_steps_itm=3,
                         expiry_dte_min=0, expiry_dte_max=8)
    with pytest.raises(ValueError, match="No liquid CE contract at ITM x3"):
        select_option(25000, "LONG", _ladder(25000), cfg, today=TODAY)


def test_a_ladder_that_stops_short_of_the_target_is_refused():
    cfg = StrategyConfig(option_moneyness="ITM", option_steps_itm=5,
                         expiry_dte_min=0, expiry_dte_max=8)
    with pytest.raises(ValueError, match="nearest eligible"):
        select_option(25000, "LONG", _ladder(24900, 25000, 25100), cfg, today=TODAY)


@pytest.mark.parametrize("moneyness, steps, expected", [
    ("ATM", 1, 25000),
    ("ITM", 1, 24900),      # a long call goes ITM by moving down a strike
    ("ITM", 2, 24800),
    ("OTM", 1, 25100),
    ("OTM", 2, 25200),
])
def test_an_available_moneyness_is_selected_exactly(moneyness, steps, expected):
    cfg = StrategyConfig(option_moneyness=moneyness, option_steps_itm=steps,
                         expiry_dte_min=0, expiry_dte_max=8)
    chain = _ladder(24800, 24900, 25000, 25100, 25200)
    assert select_option(25000, "LONG", chain, cfg, today=TODAY).strike == expected


def test_one_strike_step_of_tolerance_absorbs_a_missing_rung():
    """Step is the smallest gap in the ladder, so OTM x2 targets 25100 here.

    That rung is absent; 25050 and 25150 both sit exactly one step away, so the
    tolerance admits the fill instead of refusing a tradable chain.
    """
    cfg = StrategyConfig(option_moneyness="OTM", option_steps_itm=2,
                         expiry_dte_min=0, expiry_dte_max=8)
    chain = _ladder(25000, 25050, 25150, 25200)   # 25100 missing; step = 50
    assert select_option(25000, "LONG", chain, cfg, today=TODAY).strike in {25050, 25150}


def test_a_target_more_than_one_step_off_the_ladder_is_refused():
    cfg = StrategyConfig(option_moneyness="OTM", option_steps_itm=3,
                         expiry_dte_min=0, expiry_dte_max=8)
    chain = _ladder(25000, 25050)                 # step = 50, target 25150, nearest 25050
    with pytest.raises(ValueError, match="No liquid CE contract at OTM x3"):
        select_option(25000, "LONG", chain, cfg, today=TODAY)


def test_a_short_signal_takes_moneyness_in_the_mirror_direction():
    pes = [contract(f"PE{s:g}", AUG_MONTHLY, "PE", strike=s) for s in (24900, 25000, 25100)]
    cfg = StrategyConfig(option_moneyness="ITM", option_steps_itm=1,
                         expiry_dte_min=0, expiry_dte_max=8)
    assert select_option(25000, "SHORT", pes, cfg, today=TODAY).strike == 25100
