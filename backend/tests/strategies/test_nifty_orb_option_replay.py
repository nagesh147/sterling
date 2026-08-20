"""Option-premium replay: the fills, costs and refusals a broker would impose.

Every assertion here exists because its absence would flatter a backtest.
"""
from datetime import datetime, timedelta

import pytest

from app.engines.nifty_orb_option_replay import (
    OptionBar,
    ReplayAdmission,
    ReplayCostConfig,
    ReplayRejection,
    ReplayTrade,
    replay_signal,
    replay_trade,
    summarize_replay,
)
from app.engines.nifty_orb_options import StrategyConfig
from app.engines.nifty_orb_validation import TradingCosts

EXPIRY = "2026-01-29"


def _bar(i, low, high, close, *, open_=None, spread=1.0, volume=1_000_000, oi=50_000, expiry=EXPIRY, day=1):
    mid = close
    return OptionBar(
        timestamp=datetime(2026, 1, day, 9, 30) + timedelta(minutes=i),
        symbol="NIFTY26JAN25000CE",
        option_type="CE",
        strike=25000,
        expiry=expiry,
        open=close if open_ is None else open_,
        high=high,
        low=low,
        close=close,
        bid=mid - spread / 2,
        ask=mid + spread / 2,
        volume=volume,
        open_interest=oi,
        lot_size=75,
    )


# --------------------------------------------------------------------------
# execution timing
# --------------------------------------------------------------------------

def test_entry_fills_on_the_bar_after_the_signal():
    """The signal is known only at bar 0's close, so the fill is bar 1's open."""
    bars = [_bar(0, 100, 102, 101), _bar(1, 103, 110, 108, open_=104), _bar(2, 108, 120, 118)]
    trade = replay_trade(bars, 0, risk_points=2, target_r=2)
    assert trade is not None
    assert trade.entry_time == bars[1].timestamp
    assert trade.entry_price == pytest.approx(104 + 0.5)      # open + half spread


def test_a_same_bar_fill_must_be_asked_for_and_is_refused():
    bars = [_bar(0, 100, 102, 101), _bar(1, 103, 110, 108)]
    outcome = replay_signal(bars, 0, risk_points=2, target_r=2, entry_delay_bars=0)
    assert isinstance(outcome, ReplayRejection)
    assert "later bar" in outcome.reason


def test_a_signal_on_the_last_bar_cannot_be_filled():
    bars = [_bar(0, 100, 102, 101)]
    outcome = replay_signal(bars, 0, risk_points=2, target_r=2)
    assert isinstance(outcome, ReplayRejection)
    assert "no bar available" in outcome.reason
    assert replay_trade(bars, 0, risk_points=2, target_r=2) is None


# --------------------------------------------------------------------------
# spread and slippage
# --------------------------------------------------------------------------

def test_buying_pays_the_offer_and_selling_receives_the_bid():
    bars = [_bar(0, 100, 102, 101), _bar(1, 100, 103, 100, open_=100, spread=4.0), _bar(2, 105, 112, 110, spread=4.0)]
    trade = replay_trade(bars, 0, risk_points=3, target_r=1)
    assert trade is not None
    assert trade.entry_price == pytest.approx(102.0)          # 100 open + 2.0 half spread
    assert trade.exit_reason == "target"
    assert trade.exit_price == pytest.approx(105.0 - 2.0)     # target 105 less half spread


def test_slippage_widens_both_fills():
    """Compared on an end-of-data exit, whose reference price does not move with entry."""
    bars = [_bar(0, 100, 102, 101), _bar(1, 100, 102, 100, open_=100, spread=0.0), _bar(2, 99, 103, 101, spread=0.0)]
    clean = replay_trade(bars, 0, risk_points=50, target_r=5)
    slipped = replay_trade(bars, 0, risk_points=50, target_r=5, costs=ReplayCostConfig(slippage_points=0.5))
    assert clean is not None and slipped is not None
    assert clean.exit_reason == slipped.exit_reason == "end_of_data"
    assert slipped.entry_price == pytest.approx(clean.entry_price + 0.5)
    assert slipped.exit_price == pytest.approx(clean.exit_price - 0.5)
    assert slipped.net_pnl < clean.net_pnl


# --------------------------------------------------------------------------
# exit sequencing
# --------------------------------------------------------------------------

def test_a_bar_that_touches_both_levels_is_resolved_as_a_stop():
    """Intrabar order is unknowable, so the adverse branch is taken."""
    bars = [_bar(0, 100, 102, 101), _bar(1, 99, 101, 100, open_=100, spread=0.0), _bar(2, 90, 130, 120, spread=0.0)]
    trade = replay_trade(bars, 0, risk_points=5, target_r=2)
    assert trade is not None
    assert trade.exit_reason == "stop"
    assert trade.net_pnl < 0


def test_position_is_squared_off_on_the_expiry_date():
    bars = [
        _bar(0, 100, 102, 101, day=28, expiry="2026-01-29"),
        _bar(1, 99, 103, 100, day=28, expiry="2026-01-29", open_=100, spread=0.0),
        _bar(2, 98, 104, 99, day=29, expiry="2026-01-29", spread=0.0),
        _bar(3, 1, 200, 150, day=30, expiry="2026-01-29", spread=0.0),
    ]
    trade = replay_trade(bars, 0, risk_points=20, target_r=5)
    assert trade is not None
    assert trade.exit_reason == "expiry"
    assert trade.exit_time.date().isoformat() == "2026-01-29"


def test_running_out_of_data_is_reported_not_hidden():
    bars = [_bar(0, 100, 102, 101), _bar(1, 99, 103, 100, open_=100, spread=0.0), _bar(2, 99, 103, 101, spread=0.0)]
    trade = replay_trade(bars, 0, risk_points=50, target_r=5)
    assert trade is not None
    assert trade.exit_reason == "end_of_data"


# --------------------------------------------------------------------------
# sizing, admission and partial fills
# --------------------------------------------------------------------------

def test_quantity_is_lots_times_lot_size():
    bars = [_bar(0, 100, 102, 101), _bar(1, 103, 110, 108, open_=104), _bar(2, 108, 120, 118)]
    trade = replay_trade(bars, 0, risk_points=2, target_r=2, lots=3)
    assert trade is not None
    assert trade.quantity == 225
    assert trade.requested_quantity == 225
    assert not trade.partially_filled


def test_thin_volume_partially_fills_and_stays_lot_aligned():
    thin = _bar(1, 103, 110, 108, open_=104, volume=1000)
    bars = [_bar(0, 100, 102, 101), thin, _bar(2, 108, 120, 118)]
    admission = ReplayAdmission(max_volume_participation=0.10)   # 100 units of capacity
    trade = replay_trade(bars, 0, risk_points=2, target_r=2, lots=3, admission=admission)
    assert trade is not None
    assert trade.quantity == 75                                  # one lot, not 225
    assert trade.partially_filled


def test_volume_too_thin_for_one_lot_is_refused():
    bars = [_bar(0, 100, 102, 101), _bar(1, 103, 110, 108, open_=104, volume=100), _bar(2, 108, 120, 118)]
    outcome = replay_signal(bars, 0, risk_points=2, target_r=2, admission=ReplayAdmission(max_volume_participation=0.10))
    assert isinstance(outcome, ReplayRejection)
    assert "cannot absorb one lot" in outcome.reason


@pytest.mark.parametrize(
    "bar_kwargs, fragment",
    [
        ({"spread": 40.0}, "spread above admission ceiling"),
        ({"volume": 10}, "volume below admission floor"),
        ({"oi": 5}, "open interest below admission floor"),
    ],
)
def test_admission_refuses_what_live_would_refuse(bar_kwargs, fragment):
    bars = [_bar(0, 100, 102, 101), _bar(1, 103, 110, 108, open_=104, **bar_kwargs), _bar(2, 108, 120, 118)]
    admission = ReplayAdmission.from_strategy_config(StrategyConfig(), max_volume_participation=1.0)
    outcome = replay_signal(bars, 0, risk_points=2, target_r=2, admission=admission)
    assert isinstance(outcome, ReplayRejection)
    assert outcome.reason == fragment


def test_admission_from_strategy_config_mirrors_the_live_gates():
    cfg = StrategyConfig()
    admission = ReplayAdmission.from_strategy_config(cfg)
    assert admission.max_spread_pct == cfg.max_spread_pct
    assert admission.min_volume == cfg.min_option_volume
    assert admission.min_open_interest == cfg.min_open_interest


def test_risk_larger_than_the_premium_is_refused():
    """A bought option cannot lose more than the premium, so such a stop is fiction."""
    bars = [_bar(0, 100, 102, 101), _bar(1, 5, 12, 10, open_=10), _bar(2, 8, 20, 18)]
    outcome = replay_signal(bars, 0, risk_points=50, target_r=2)
    assert isinstance(outcome, ReplayRejection)
    assert "exceeds the premium" in outcome.reason


# --------------------------------------------------------------------------
# costs
# --------------------------------------------------------------------------

def test_flat_costs_are_charged_on_both_orders():
    bars = [_bar(0, 100, 102, 101), _bar(1, 99, 103, 100, open_=100, spread=0.0), _bar(2, 90, 103, 95, spread=0.0)]
    trade = replay_trade(bars, 0, risk_points=2, target_r=2,
                         costs=ReplayCostConfig(brokerage_per_order=10, charges_per_order=5))
    assert trade is not None
    assert trade.exit_reason == "stop"
    assert trade.costs == 30


def test_statutory_charges_scale_with_turnover():
    bars = [_bar(0, 100, 102, 101), _bar(1, 100, 102, 100, open_=100, spread=0.0), _bar(2, 105, 112, 110, spread=0.0)]
    flat = replay_trade(bars, 0, risk_points=3, target_r=1)
    costed = replay_trade(bars, 0, risk_points=3, target_r=1,
                          costs=ReplayCostConfig(statutory=TradingCosts(slippage_per_share=0.0)))
    assert flat is not None and costed is not None
    assert flat.costs == 0
    assert costed.costs > 0
    assert costed.gross_pnl == pytest.approx(flat.gross_pnl)
    assert costed.net_pnl < flat.net_pnl


def test_statutory_slippage_would_double_count_and_is_rejected():
    with pytest.raises(ValueError, match="double-counts"):
        ReplayCostConfig(slippage_points=0.5, statutory=TradingCosts(slippage_per_share=0.10))


# --------------------------------------------------------------------------
# excursions and summary
# --------------------------------------------------------------------------

def test_excursions_are_measured_over_the_holding_period():
    bars = [_bar(0, 100, 102, 101), _bar(1, 95, 103, 100, open_=100, spread=0.0), _bar(2, 105, 112, 110, spread=0.0)]
    trade = replay_trade(bars, 0, risk_points=8, target_r=1, lots=1)
    assert trade is not None
    assert trade.max_adverse_excursion == pytest.approx((100 - 95) * 75)
    assert trade.max_favourable_excursion == pytest.approx((112 - 100) * 75)


def test_summary_separates_gross_from_net_and_reports_exit_reasons():
    win = [_bar(0, 100, 102, 101), _bar(1, 100, 102, 100, open_=100, spread=0.0), _bar(2, 105, 112, 110, spread=0.0)]
    loss = [_bar(0, 100, 102, 101), _bar(1, 99, 101, 100, open_=100, spread=0.0), _bar(2, 90, 100, 95, spread=0.0)]
    costs = ReplayCostConfig(brokerage_per_order=20)
    trades = [
        replay_trade(win, 0, risk_points=3, target_r=1, costs=costs),
        replay_trade(loss, 0, risk_points=3, target_r=1, costs=costs),
    ]
    assert all(isinstance(t, ReplayTrade) for t in trades)
    metrics = summarize_replay(trades)
    assert metrics["trades"] == 2
    assert metrics["exit_reasons"] == {"target": 1, "stop": 1}
    assert metrics["total_costs"] == 80
    assert metrics["net_pnl"] == pytest.approx(metrics["gross_pnl"] - 80)
    assert metrics["profit_factor"] < metrics["gross_profit_factor"]
    assert metrics["max_consecutive_losses"] == 1


def test_empty_summary_reports_zeroes_not_infinity():
    metrics = summarize_replay([])
    assert metrics["trades"] == 0
    assert metrics["profit_factor"] == 0.0
    assert metrics["exit_reasons"] == {}
