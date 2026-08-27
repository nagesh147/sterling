"""A plan that sizes to zero lots is not a trade, and must not look like one.

ORB sizes against the full premium outlay, deliberately: a bought option can
expire worthless, so the outlay *is* the risk, and this matches the ceiling the
live executor applies. The consequence is that one lot must fit inside
``max_risk_inr`` or nothing can be bought at all --

    lots = int(max_risk_inr // (entry_premium * lot_size))

-- and with a 3,000 rupee cap against a NIFTY put at 69.45 x 65 = 4,514 per lot,
that floors to zero on every instrument in the universe. The plan was still
emitted, with ``quantity=0``, ``risk_inr=0`` and ``max_loss_inr=0``: a row that
reads as a live setup and can never be filled.

Refusing is what makes the cap legible. The message carries the two numbers the
operator needs -- what one lot costs, and what the cap is -- so the fix is a
decision rather than an investigation.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import (
    OptionContract,
    Signal,
    StrategyConfig,
    build_trade_plan,
)

IST = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 8, 27, 11, 0, tzinfo=IST)


def _signal(direction: str = "LONG") -> Signal:
    return Signal(
        direction=direction, regime="TREND", timestamp=NOW, or_high=24012.0,
        or_low=23988.0, vwap=24000.0, atr=20.0, breakout_distance=8.0,
        volume_ratio=1.4, confidence=0.7, reason="test",
    )


def _option(premium: float, lot_size: int, option_type: str = "CE") -> OptionContract:
    return OptionContract(
        symbol=f"NIFTY26SEP24100{option_type}", strike=24100.0, expiry="2026-09-29",
        option_type=option_type, ltp=premium, bid=premium - 0.5, ask=premium,
        lot_size=lot_size, volume=50000.0, open_interest=900000.0,
    )


def test_a_cap_below_one_lot_is_refused_not_silently_zeroed():
    cfg = StrategyConfig(max_risk_inr=3000.0)

    with pytest.raises(ValueError) as exc:
        build_trade_plan(_signal(), _option(69.45, 65), cfg, spot=24090.0, now=NOW)

    message = str(exc.value)
    assert "4514" in message.replace(",", "")   # what one lot actually costs
    assert "3000" in message.replace(",", "")   # the cap that blocked it
    assert "max_risk_inr" in message


def test_the_refusal_names_the_lot_arithmetic_for_an_expensive_index():
    """BANKNIFTY at 820 x 30 needs ~24,600 -- eight times the configured cap."""
    cfg = StrategyConfig(max_risk_inr=3000.0)

    with pytest.raises(ValueError, match=r"24,603"):
        build_trade_plan(_signal("SHORT"), _option(820.1, 30, "PE"), cfg,
                         spot=57509.0, now=NOW)


def test_a_cap_that_affords_one_lot_still_builds_a_plan():
    cfg = StrategyConfig(max_risk_inr=5000.0)

    plan = build_trade_plan(_signal(), _option(69.45, 65), cfg, spot=24090.0, now=NOW)

    assert plan.quantity == 65
    assert plan.max_loss_inr == pytest.approx(69.45 * 65)


def test_a_larger_cap_still_sizes_in_whole_lots():
    cfg = StrategyConfig(max_risk_inr=15000.0)

    plan = build_trade_plan(_signal(), _option(69.45, 65), cfg, spot=24090.0, now=NOW)

    assert plan.quantity == 3 * 65          # 15000 // 4514 == 3
    assert plan.max_loss_inr <= cfg.max_risk_inr


def test_a_cheap_contract_is_unaffected():
    """The guard must only fire where one lot genuinely does not fit."""
    cfg = StrategyConfig(max_risk_inr=3000.0)

    plan = build_trade_plan(_signal(), _option(4.0, 500), cfg, spot=24090.0, now=NOW)

    assert plan.quantity == 500             # 3000 // 2000 == 1 lot
