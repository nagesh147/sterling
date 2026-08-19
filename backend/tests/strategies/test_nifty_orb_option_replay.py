from datetime import datetime, timedelta

from app.engines.nifty_orb_option_replay import OptionBar, ReplayCostConfig, replay_trade, summarize_replay


def _bar(i: int, low: float, high: float, close: float) -> OptionBar:
    return OptionBar(datetime(2026, 1, 1, 9, 30) + timedelta(minutes=i), "NIFTY26JAN25000CE", "CE", 25000, "2026-01-29", close, high, low, close, bid=close - 0.5, ask=close + 0.5, lot_size=75)


def test_option_replay_uses_option_prices_and_lot_size():
    bars = [_bar(0, 100, 102, 101), _bar(1, 102, 110, 108)]
    trade = replay_trade(bars, 0, risk_points=2, target_r=2)
    assert trade is not None
    assert trade.quantity == 75
    assert trade.exit_reason == "target"
    assert trade.entry_price == 101.5
    assert trade.exit_price == 107.5


def test_option_replay_applies_costs():
    bars = [_bar(0, 100, 102, 101), _bar(1, 99, 102, 100)]
    trade = replay_trade(bars, 0, risk_points=2, target_r=2, costs=ReplayCostConfig(brokerage_per_order=10, charges_per_order=5))
    assert trade is not None
    assert trade.exit_reason == "stop"
    assert trade.costs == 30


def test_replay_rejects_last_bar_entry_to_prevent_same_candle_exit():
    bars = [_bar(0, 100, 102, 101)]
    assert replay_trade(bars, 0, risk_points=2, target_r=2) is None


def test_replay_summary_reports_profit_factor_and_drawdown():
    bars = [_bar(0, 100, 102, 101), _bar(1, 102, 110, 108)]
    trade = replay_trade(bars, 0, risk_points=2, target_r=2)
    assert trade is not None
    metrics = summarize_replay([trade])
    assert metrics["trades"] == 1
    assert metrics["win_rate"] == 1.0
    assert metrics["profit_factor"] == float("inf")
