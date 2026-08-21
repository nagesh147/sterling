"""Stop-loss and trailing-stop behaviour.

The observed bot had no stop at all: it took a fixed +15 and wore whatever the
downside was. These policies are ours, not the recording's, so the tests here
are about the safety property rather than fidelity to a video.

The property that matters is the **ratchet**: a stop that can move down is not
protection, it is a way to lose more than was agreed. Everything else is detail.
"""
import pytest

from app.engines.atm_premium_imbalance import ATMPremiumImbalanceConfig
from app.engines.atm_premium_imbalance.exit import (
    should_exit, stop_price, trailing_stop_price,
)


def trailing(**kw) -> ATMPremiumImbalanceConfig:
    base = dict(enabled=True, exit_policy="TRAILING_STOP", stop_enabled=True,
                stop_basis="PERCENT", stop_percent=20.0, trail_percent=10.0,
                trail_start_percent=10.0, breakeven_percent=5.0, target_points=0.0)
    base.update(kw)
    return ATMPremiumImbalanceConfig(**base).validate()


# ------------------------------------------------------------------ the ladder

def test_before_any_gain_the_stop_is_the_agreed_risk():
    cfg = trailing()
    assert trailing_stop_price(100.0, 100.0, cfg) == 80.0        # 20% of entry


def test_a_gain_too_small_to_reach_breakeven_moves_nothing():
    cfg = trailing()
    assert trailing_stop_price(100.0, 104.0, cfg) == 80.0        # needs +5


def test_reaching_breakeven_moves_the_stop_to_the_entry_fill():
    """After this the trade cannot lose, which is the whole reason for it."""
    cfg = trailing()
    assert trailing_stop_price(100.0, 106.0, cfg) == 100.0


def test_the_trail_follows_the_high_water_mark():
    cfg = trailing()
    assert trailing_stop_price(100.0, 120.0, cfg) == 108.0       # 120 - 10% of 120
    assert trailing_stop_price(100.0, 150.0, cfg) == 135.0


def test_the_trail_never_pulls_the_stop_back_below_breakeven():
    """At +10 the raw trail is 99 — below entry. Breakeven has to win."""
    cfg = trailing()
    assert trailing_stop_price(100.0, 110.0, cfg) == 100.0


@pytest.mark.parametrize("peak", [100, 101, 105, 110, 130, 200, 500])
def test_the_stop_never_moves_down_as_the_peak_rises(peak):
    """The ratchet, stated directly: monotonic in the high-water mark."""
    cfg = trailing()
    stops = [trailing_stop_price(100.0, p, cfg) for p in range(100, peak + 1)]
    assert stops == sorted(stops)


def test_percent_distances_are_measured_from_the_entry_fill():
    """The risk agreed at entry must not drift with the market.

    The trail distance is the deliberate exception — it follows the peak.
    """
    cfg = trailing(stop_percent=25.0, trail_percent=0.0, breakeven_percent=0.0)
    assert trailing_stop_price(400.0, 400.0, cfg) == 300.0       # 25% of 400
    assert trailing_stop_price(400.0, 900.0, cfg) == 300.0       # unchanged by the peak


def test_points_basis_is_an_absolute_distance():
    cfg = trailing(stop_basis="POINTS", stop_points=15.0, trail_points=8.0,
                   trail_start_points=8.0, breakeven_points=4.0)
    assert trailing_stop_price(100.0, 100.0, cfg) == 85.0
    assert trailing_stop_price(100.0, 120.0, cfg) == 112.0


def test_the_same_number_means_different_risk_on_different_premiums():
    """Why PERCENT exists: 15 points is 30% of a 50 premium and 3% of a 500."""
    pts = trailing(stop_basis="POINTS", stop_points=15.0, trail_points=0.0,
                   trail_start_points=0.0, breakeven_points=0.0)
    assert trailing_stop_price(50.0, 50.0, pts) == 35.0          # risking 30%
    assert trailing_stop_price(500.0, 500.0, pts) == 485.0       # risking 3%
    pct = trailing(trail_percent=0.0, trail_start_percent=0.0, breakeven_percent=0.0)
    assert trailing_stop_price(50.0, 50.0, pct) == 40.0          # both 20%
    assert trailing_stop_price(500.0, 500.0, pct) == 400.0


def test_a_stop_can_never_be_negative():
    cfg = trailing(stop_basis="POINTS", stop_points=500.0, trail_points=0.0,
                   trail_start_points=0.0, breakeven_points=0.0)
    assert trailing_stop_price(100.0, 100.0, cfg) == 0.0


# ------------------------------------------------------------------- exiting

def test_trailing_mode_exits_when_the_price_falls_to_the_trailed_stop():
    cfg = trailing()
    assert should_exit(last_price=134.0, entry_fill=100.0, cfg=cfg,
                       high_water=150.0) == (True, "trailing_stop_hit")
    assert should_exit(last_price=136.0, entry_fill=100.0, cfg=cfg,
                       high_water=150.0) == (False, "")


def test_the_three_rungs_are_named_apart():
    """"Stopped out" and "gave back part of a win" are different outcomes."""
    cfg = trailing()
    assert should_exit(last_price=79.0, entry_fill=100.0, cfg=cfg,
                       high_water=100.0)[1] == "stop_hit"
    assert should_exit(last_price=99.0, entry_fill=100.0, cfg=cfg,
                       high_water=106.0)[1] == "breakeven_stop_hit"
    assert should_exit(last_price=130.0, entry_fill=100.0, cfg=cfg,
                       high_water=150.0)[1] == "trailing_stop_hit"


def test_trailing_mode_has_no_ceiling_by_default():
    """A target would cap exactly the runs a trail exists to keep."""
    cfg = trailing()
    assert should_exit(last_price=10_000.0, entry_fill=100.0, cfg=cfg,
                       high_water=10_000.0) == (False, "")


def test_a_target_still_applies_if_the_operator_asks_for_one():
    cfg = trailing(target_points=15.0)
    assert should_exit(last_price=116.0, entry_fill=100.0, cfg=cfg,
                       high_water=116.0) == (True, "target_hit")


def test_omitting_the_high_water_mark_does_not_silently_arm_the_trail():
    """Defaulting to last_price would make every price its own peak.

    The trail would then sit permanently just under the market and fire at the
    first tick down, so the default is the entry fill: no gain yet.
    """
    cfg = trailing()
    assert should_exit(last_price=150.0, entry_fill=100.0, cfg=cfg) == (False, "")


def test_the_time_stop_still_applies_while_trailing():
    cfg = trailing(max_hold_seconds=60)
    assert should_exit(last_price=105.0, entry_fill=100.0, cfg=cfg,
                       high_water=105.0, held_seconds=61) == (True, "time_stop")


# ------------------------------------------------------------------ the config

def test_the_observed_policy_is_untouched_by_all_of_this():
    """FIXED_POINT_TARGET must still be the recording's behaviour exactly."""
    cfg = ATMPremiumImbalanceConfig(enabled=True, target_points=15.0).validate()
    assert stop_price(133.40, cfg) is None                       # no stop observed
    assert should_exit(last_price=148.40, entry_fill=133.40, cfg=cfg) == (True, "target_hit")
    assert should_exit(last_price=148.39, entry_fill=133.40, cfg=cfg) == (False, "")


def test_trailing_without_a_floor_is_refused():
    """A trail with no initial stop is not a stop, it is a hope."""
    with pytest.raises(ValueError, match="requires stop_enabled"):
        ATMPremiumImbalanceConfig(enabled=True, exit_policy="TRAILING_STOP",
                                  target_points=0.0).validate()


def test_a_hundred_percent_stop_is_refused():
    with pytest.raises(ValueError, match="below 100"):
        ATMPremiumImbalanceConfig(enabled=True, stop_enabled=True, stop_basis="PERCENT",
                                  stop_percent=100.0).validate()


def test_no_target_is_only_allowed_where_it_means_something():
    with pytest.raises(ValueError, match="target_points must be > 0"):
        ATMPremiumImbalanceConfig(enabled=True, target_points=0.0).validate()


# ------------------------------------------------- reporting what there is not

def test_a_policy_with_no_ceiling_reports_no_target():
    """entry + 0 is the entry, and calling that a target reads as zero profit."""
    from app.engines.atm_premium_imbalance.exit import optional_target_price
    assert optional_target_price(268.65, trailing()) is None


def test_the_observed_policy_still_reports_its_target():
    from app.engines.atm_premium_imbalance.exit import optional_target_price
    cfg = ATMPremiumImbalanceConfig(enabled=True, target_points=15.0).validate()
    assert optional_target_price(133.40, cfg) == 148.40


def test_a_trailing_trade_carries_no_target_on_the_record():
    """The board must not draw a target line where there is no target."""
    from .test_golden_trades import ScriptedBroker, drive, make_pair
    from app.engines.atm_premium_imbalance import ATMPremiumImbalanceStrategy
    cfg = trailing(stop_percent=15.0, trail_percent=8.0, trail_start_percent=5.0,
                   breakeven_percent=3.0)
    s = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=make_pair(77700.0, "ACE", "APE", "2026-08-27", upper=3000.0),
        quantity=20, trade_id="t")
    drive(s, ScriptedBroker(entry_fill=268.65, exit_fill=290.80), [
        ("CE", 584.90, 584.0, 585.0), ("PE", 267.60, 267.1, 268.1),
    ])
    assert s.trade is not None and s.trade.entry_price == 268.65
    assert s.trade.target_price is None
    assert s.live_stop == 228.35            # 268.65 x 0.85

