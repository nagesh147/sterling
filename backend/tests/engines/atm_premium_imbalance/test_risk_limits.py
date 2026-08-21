"""The two limits that used to be decoration.

`max_premium_at_risk_inr` and `daily_loss_limit_inr` were config fields with
nothing reading them: they looked like protection and were not. These tests exist
so that cannot quietly happen again.

Neither limit can be switched off — the config refuses a zero or negative value.
That is deliberate and stricter than an "0 means unlimited" convention, which is
one typo away from no protection at all.
"""
import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, PremiumPairView,
)
from app.engines.atm_premium_imbalance.signal import evaluate

from .test_golden_trades import ScriptedBroker, drive, make_pair

# CE dear, PE cheap: buys the put at ask 337.60 + 0.50 buffer = 338.10.
OPEN_TICKS = [("CE", 491.15, 490.5, 491.6), ("PE", 337.15, 336.6, 337.6)]


def _strategy(**kw):
    base = dict(enabled=True, quantity=80)
    base.update(kw)
    cfg = ATMPremiumImbalanceConfig(**base).validate()
    pair = make_pair(77700.0, "ACE", "APE", "2026-08-27", upper=3000.0)
    return ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=80, trade_id="t")


# ---------------------------------------------- premium at risk, at entry time

def test_an_entry_over_the_premium_ceiling_is_refused():
    """80 contracts at 338.10 is Rs27,048 — over the Rs25,000 default.

    Worth stating plainly: the default ceiling would have refused the trade the
    recording actually took.
    """
    s = _strategy(max_premium_at_risk_inr=25_000.0)
    intent = drive(s, ScriptedBroker(entry_fill=340.10, exit_fill=356.0), OPEN_TICKS)
    assert intent.kind == "halt"
    assert "premium_at_risk_exceeded" in intent.reason
    assert s.trade is None or s.trade.entry_price is None


def test_the_same_entry_is_allowed_under_a_ceiling_that_covers_it():
    s = _strategy(max_premium_at_risk_inr=40_000.0)
    drive(s, ScriptedBroker(entry_fill=340.10, exit_fill=356.0), OPEN_TICKS)
    assert s.trade is not None and s.trade.entry_price == 340.10


def test_the_ceiling_is_measured_on_the_limit_price_not_the_last_price():
    """What can be lost is what is paid, and that is the limit we send.

    338.10 x 80 = 27,048, but 337.15 (the LTP) x 80 = 26,972 — under a 27,000
    ceiling. An LTP-based check would pass the order and then overspend.
    """
    s = _strategy(max_premium_at_risk_inr=27_000.0)
    assert drive(s, ScriptedBroker(entry_fill=340.10, exit_fill=356.0),
                 OPEN_TICKS).kind == "halt"


def test_a_smaller_size_brings_the_same_premium_under_the_ceiling():
    """The ceiling constrains size, not the strategy: 40 x 338.10 = Rs13,524."""
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=40,
                                    max_premium_at_risk_inr=25_000.0).validate()
    pair = make_pair(77700.0, "ACE", "APE", "2026-08-27", upper=3000.0)
    s = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=40, trade_id="t")
    drive(s, ScriptedBroker(entry_fill=340.10, exit_fill=356.0), OPEN_TICKS)
    assert s.trade is not None and s.trade.entry_price == 340.10


def test_the_ceiling_cannot_be_switched_off():
    for value in (0.0, -1.0):
        with pytest.raises(ValueError, match="max_premium_at_risk_inr must be > 0"):
            ATMPremiumImbalanceConfig(enabled=True, max_premium_at_risk_inr=value).validate()


# ------------------------------------------------------------- daily loss limit

def _view(ce=200.0, pe=150.0):
    return PremiumPairView(mode="COMPATIBILITY", ce_price=ce, pe_price=pe)


def _multi_trade_cfg(**kw):
    base = dict(enabled=True, quantity=20, max_trades_per_session=5,
                daily_loss_limit_inr=10_000.0)
    base.update(kw)
    return ATMPremiumImbalanceConfig(**base).validate()


def test_a_breached_daily_loss_limit_stops_further_trades():
    sig = evaluate(_view(), _multi_trade_cfg(), realised_pnl=-10_000.0)
    assert sig.action == "NO_TRADE"
    assert sig.reason == "daily_loss_limit_reached"


def test_a_loss_short_of_the_limit_still_trades():
    assert evaluate(_view(), _multi_trade_cfg(), realised_pnl=-9_999.99).action == "BUY_PE"


def test_profit_never_trips_the_loss_limit():
    """The sign matters: a good day must not look like a breach."""
    assert evaluate(_view(), _multi_trade_cfg(), realised_pnl=50_000.0).action == "BUY_PE"


def test_the_limit_is_checked_before_the_quote_arithmetic():
    """A breached limit must not be argued with by an attractive price."""
    cfg = _multi_trade_cfg(daily_loss_limit_inr=5_000.0)
    sig = evaluate(_view(ce=900.0, pe=1.0), cfg, realised_pnl=-6_000.0)
    assert sig.reason == "daily_loss_limit_reached"


def test_the_limit_cannot_be_switched_off():
    for value in (0.0, -1.0):
        with pytest.raises(ValueError, match="daily_loss_limit_inr must be > 0"):
            ATMPremiumImbalanceConfig(enabled=True, daily_loss_limit_inr=value).validate()


def test_no_realised_loss_yet_is_not_a_breach():
    """The default must not read as "already down Rs0, therefore stop"."""
    assert evaluate(_view(), _multi_trade_cfg()).action == "BUY_PE"


def test_a_closed_trade_books_its_pnl_so_the_limit_can_see_it():
    """The accumulator is what makes the limit real across trades."""
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=20, target_points=15.0,
                                   max_premium_at_risk_inr=40_000.0).validate()
    pair = make_pair(77700.0, "ACE", "APE", "2026-08-27", upper=3000.0)
    s = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=20, trade_id="t")
    drive(s, ScriptedBroker(entry_fill=133.40, exit_fill=156.85), [
        ("CE", 167.50, 167.0, 167.50), ("PE", 214.85, 214.4, 215.3),
        ("CE", 149.10, 149.2, 149.6),
    ])
    assert s.trades_taken == 1
    assert s.realised_pnl == pytest.approx(s.trade.pnl)
    assert s.summary()["realised_pnl"] == pytest.approx(s.trade.pnl)
