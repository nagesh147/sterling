from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import OptionContract, Signal, StrategyConfig, build_trade_plan, select_option

IST = timezone(timedelta(hours=5, minutes=30))


def contract(symbol, expiry, typ, strike=25000, volume=5000, oi=20000, bid=99, ask=101):
    return OptionContract(symbol, strike, expiry, typ, 100, bid, ask, 65, 0.5, volume, oi)


def test_expiry_dte_range_is_enforced():
    cfg = StrategyConfig(expiry_selection="nearest", expiry_dte_min=0, expiry_dte_max=2, truedata_use_quote_freshness=False)
    contracts = [
        contract("FAR", "2099-12-31", "CE"),
        contract("NEAR", (datetime.now().date() + timedelta(days=1)).isoformat(), "CE"),
    ]
    chosen = select_option(25010, "LONG", contracts, cfg)
    assert chosen.symbol == "NEAR"


def test_weekly_and_monthly_selection_are_distinct():
    cfg = StrategyConfig(expiry_selection="weekly", expiry_dte_min=0, expiry_dte_max=60, truedata_use_quote_freshness=False)
    weekly = (datetime.now().date() + timedelta(days=7)).isoformat()
    monthly = (datetime.now().date() + timedelta(days=30)).isoformat()
    contracts = [contract("W", weekly, "CE"), contract("M", monthly, "CE")]
    chosen = select_option(25000, "LONG", contracts, cfg)
    assert chosen.symbol == "W"


def test_buy_only_direction_mapping_is_strict():
    cfg = StrategyConfig(truedata_use_quote_freshness=False)
    ce = contract("CE", (datetime.now().date() + timedelta(days=1)).isoformat(), "CE")
    pe = contract("PE", (datetime.now().date() + timedelta(days=1)).isoformat(), "PE")
    assert select_option(25000, "LONG", [ce, pe], cfg).option_type == "CE"
    assert select_option(25000, "SHORT", [ce, pe], cfg).option_type == "PE"


def test_wide_spread_is_rejected():
    cfg = StrategyConfig(max_spread_pct=1.0)
    wide = contract("WIDE", (datetime.now().date() + timedelta(days=1)).isoformat(), "CE", bid=80, ask=120)
    with pytest.raises(ValueError, match="liquid"):
        select_option(25000, "LONG", [wide], cfg)


def test_trade_plan_rejects_mismatched_option_side():
    cfg = StrategyConfig(truedata_use_quote_freshness=False)
    signal = Signal("LONG", "TREND", datetime.now(IST), 25000, 24900, 25010, 50, 20, 2, 0.8, "test")
    pe = contract("PE", (datetime.now().date() + timedelta(days=1)).isoformat(), "PE")
    with pytest.raises(ValueError, match="does not match"):
        build_trade_plan(signal, pe, cfg, spot=25020)
