from datetime import date, datetime, timezone

import pytest

from app.engines.nifty_orb_options import OptionContract, Signal, StrategyConfig
from app.engines.nifty_orb_universe import UniverseInstrument, UniverseSignal
from app.services.nifty_orb_trade_planner import plan_signal, signal_to_spot


def _signal(direction: str) -> Signal:
    return Signal(
        direction=direction,
        regime="TREND",
        timestamp=datetime.now(timezone.utc),
        or_high=100.0,
        or_low=90.0,
        vwap=98.0 if direction == "LONG" else 92.0,
        atr=2.0,
        breakout_distance=2.0,
        volume_ratio=1.5,
        confidence=0.85,
        reason="test",
    )


TODAY = date(2026, 8, 20)
EXPIRY = "2026-08-27"       # 7 DTE from TODAY, inside the 0-7 default range


def _contract(symbol: str, strike: float, option_type: str) -> OptionContract:
    return OptionContract(
        symbol=symbol,
        strike=strike,
        expiry=EXPIRY,
        option_type=option_type,
        # One lot must fit the risk budget (50.25 x 50 = Rs 2,513 under Rs 3,000)
        # and the 1.0% spread must clear the 1.5% default ceiling.
        ltp=50.0,
        bid=49.75,
        ask=50.25,
        lot_size=50,
        delta=0.7,
        volume=5000,
        open_interest=50000,
    )


def test_long_signal_can_only_plan_a_ce_buy():
    cfg = StrategyConfig(max_risk_inr=3000)
    candidate = UniverseSignal(UniverseInstrument("SBIN", "stock"), _signal("LONG"))
    planned = plan_signal(
        candidate,
        [_contract("SBIN_CE", 100, "CE"), _contract("SBIN_PE", 100, "PE")],
        cfg,
        today=TODAY,
    )
    assert planned.option.option_type == "CE"
    assert planned.trade_plan.direction == "LONG"
    assert planned.trade_plan.quantity > 0
    assert planned.trade_plan.risk_inr <= cfg.max_risk_inr
    # The binding ceiling is the full premium, because a bought option can expire
    # worthless -- and it is the same ceiling the live executor applies.
    assert planned.trade_plan.max_loss_inr <= cfg.max_risk_inr
    assert planned.trade_plan.max_loss_inr == planned.trade_plan.quantity * planned.trade_plan.entry_premium


def test_short_signal_can_only_plan_a_pe_buy():
    cfg = StrategyConfig(max_risk_inr=3000)
    candidate = UniverseSignal(UniverseInstrument("SBIN", "stock"), _signal("SHORT"))
    planned = plan_signal(
        candidate,
        [_contract("SBIN_CE", 90, "CE"), _contract("SBIN_PE", 90, "PE")],
        cfg,
        today=TODAY,
    )
    assert planned.option.option_type == "PE"
    assert planned.trade_plan.direction == "SHORT"
    assert planned.trade_plan.quantity > 0
    assert planned.trade_plan.risk_inr <= cfg.max_risk_inr


def test_spot_reconstruction_matches_breakout_definition():
    assert signal_to_spot(_signal("LONG")) == pytest.approx(102.0)
    assert signal_to_spot(_signal("SHORT")) == pytest.approx(88.0)


def test_neutral_signal_is_rejected():
    candidate = UniverseSignal(UniverseInstrument("SBIN", "stock"), _signal("NONE"))
    with pytest.raises(ValueError):
        plan_signal(candidate, [_contract("SBIN_CE", 100, "CE")], StrategyConfig(), today=TODAY)


def test_no_liquid_option_is_rejected():
    cfg = StrategyConfig(max_spread_pct=1.0)
    candidate = UniverseSignal(UniverseInstrument("SBIN", "stock"), _signal("LONG"))
    wide = OptionContract(
        symbol="SBIN_CE", strike=100, expiry=EXPIRY, option_type="CE",
        ltp=100, bid=90, ask=110, lot_size=50, volume=5000, open_interest=50000,
    )
    with pytest.raises(ValueError):
        plan_signal(candidate, [wide], cfg, today=TODAY)
