"""The plan an operator reads must be the plan that executes.

`build_trade_plan` sized against the modelled stop distance while the live
executor sized against the full premium outlay. On a modest breakout the two
disagreed by 16x: the board showed 2400 units of an 18-rupee option -- 43,200
rupees of premium -- labelled "risk 3,000", while the executor would buy 150.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import OptionContract, Signal, StrategyConfig, build_trade_plan
from app.services.nifty_orb_execution import _conservative_quantity

IST = timezone(timedelta(hours=5, minutes=30))


def _signal(atr=14.0, breakout=5.0, direction="LONG"):
    return Signal(direction, "TREND", datetime.now(IST), 24012, 23988, 24000, atr, breakout, 2.0, 0.8, "test")


def _option(premium=18.0, lot_size=75, delta=0.5):
    return OptionContract("NIFTYCE", 24000, "2026-08-27", "CE", ltp=premium, bid=premium - 0.05,
                          ask=premium, lot_size=lot_size, delta=delta, volume=5000, open_interest=50000)


@pytest.mark.parametrize("premium, lot_size, budget", [
    (18.0, 75, 3000.0),      # the reported case
    (18.0, 75, 50000.0),
    (2.5, 50, 3000.0),       # cheap option, generous lot count
    (250.0, 25, 20000.0),    # expensive option
])
@pytest.mark.parametrize("atr, breakout", [(14.0, 5.0), (14.0, 90.0), (40.0, 2.0)])
def test_plan_quantity_equals_what_the_executor_will_buy(premium, lot_size, budget, atr, breakout):
    option = _option(premium, lot_size)
    cfg = StrategyConfig(max_risk_inr=budget)
    plan = build_trade_plan(_signal(atr, breakout), option, cfg, spot=24017)
    assert plan.quantity == _conservative_quantity(plan.quantity, lot_size, option.ask, budget)


def test_the_premium_outlay_never_exceeds_the_risk_budget():
    cfg = StrategyConfig(max_risk_inr=3000)
    plan = build_trade_plan(_signal(), _option(), cfg, spot=24017)
    assert plan.max_loss_inr == plan.quantity * plan.entry_premium
    assert plan.max_loss_inr <= cfg.max_risk_inr
    assert plan.quantity == 150 and plan.entry_premium == 18.0


def test_the_modelled_stop_loss_cannot_exceed_the_premium_paid():
    """A stop wider than the premium used to produce a 0.05 "stop" -- hold to zero."""
    plan = build_trade_plan(_signal(atr=14.0, breakout=200.0), _option(premium=18.0),
                            StrategyConfig(max_risk_inr=3000), spot=24017)
    assert plan.premium_risk_per_share <= plan.entry_premium
    assert plan.risk_inr <= plan.max_loss_inr
    assert plan.stop_premium >= 0.05


def test_a_budget_below_one_lot_is_refused_rather_than_sized_to_zero():
    """Parity is about the outcome, and both sides refuse.

    This used to assert a ``quantity=0`` plan. The executor never filled one --
    `execute_scan` blocks at ``quantity<=0`` with "one option lot exceeds
    conservative premium risk budget" -- so the plan was a row that looked live,
    priced, and actionable while being none of those things. The planner raises
    the same refusal at scan time instead, carrying the two numbers that decide
    it, and `_conservative_quantity` still agrees there is nothing to buy.
    """
    with pytest.raises(ValueError, match="above the max_risk_inr cap"):
        build_trade_plan(_signal(), _option(premium=100.0, lot_size=75),
                         StrategyConfig(max_risk_inr=3000), spot=24017)

    assert _conservative_quantity(75, 75, 100.0, 3000.0) == 0


def test_quantity_stays_lot_aligned():
    for lot_size in (25, 50, 65, 75):
        plan = build_trade_plan(_signal(), _option(premium=7.0, lot_size=lot_size),
                                StrategyConfig(max_risk_inr=3000), spot=24017)
        assert plan.quantity % lot_size == 0


def test_manual_adapter_and_auto_plan_share_one_fingerprint():
    """Board ticket fields === execute_scan plan fields for the same row."""
    from app.services.nifty_orb_lifecycle import SAME_TICKET_FIELDS, attach_ticket, ticket_fields, ticket_fingerprint

    cfg = StrategyConfig(max_risk_inr=3000)
    plan = build_trade_plan(_signal(), _option(), cfg, spot=24017)
    row = {
        "status": "signal",
        "underlying": "NIFTY",
        "signal": {"direction": "LONG", "timestamp": "2026-08-25T10:30:00+05:30"},
        "trade": plan.to_dict(),
    }
    attach_ticket(row)
    auto = ticket_fields(plan.to_dict())
    assert row["ticket"] == auto
    assert set(auto) == set(SAME_TICKET_FIELDS)
    assert row["ticket_fingerprint"] == ticket_fingerprint(plan.to_dict(), row["signal"])
    assert auto["symbol"] == "NIFTYCE"
    assert auto["option_type"] == "CE"
    assert auto["quantity"] == plan.quantity
    assert auto["stop_premium"] == plan.stop_premium
    assert auto["target_premium"] == plan.target_premium
    assert auto["lot_size"] == 75


def test_the_plan_dict_carries_the_honest_max_loss():
    plan = build_trade_plan(_signal(), _option(), StrategyConfig(max_risk_inr=3000), spot=24017)
    payload = plan.to_dict()
    assert payload["max_loss_inr"] == plan.max_loss_inr
    assert payload["risk_inr"] == plan.risk_inr


def test_an_assumed_delta_is_flagged_on_the_plan():
    """Kite publishes no Greeks, so 0.50 is assumed -- and stop_premium is armed
    at the broker from it. The plan must say the number rests on an assumption."""
    estimated = build_trade_plan(_signal(), _option(delta=None),
                                 StrategyConfig(max_risk_inr=3000), spot=24017)
    known = build_trade_plan(_signal(), _option(delta=0.25),
                             StrategyConfig(max_risk_inr=3000), spot=24017)
    assert estimated.delta_is_estimated is True
    assert known.delta_is_estimated is False
    assert estimated.to_dict()["delta_is_estimated"] is True
    # The assumption is not cosmetic: it moves the premium-domain stop.
    assert estimated.stop_premium != known.stop_premium
