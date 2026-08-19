from datetime import datetime, timedelta

from app.engines.nifty_orb_options import (
    Bar,
    OptionContract,
    Signal,
    StrategyConfig,
    build_trade_plan,
    generate_signal,
    select_option,
)


def _bars(direction: str) -> list[Bar]:
    start = datetime(2026, 8, 19, 9, 15)
    rows = []
    price = 100.0
    for i in range(30):
        ts = start + timedelta(minutes=5 * i)
        if i < 3:
            close = 100.0 + i * 0.2
            high = close + 0.5
            low = close - 0.5
        elif direction == "LONG":
            close = 101.0 + (i - 3) * 0.8
            high = close + 0.4
            low = close - 0.3
        else:
            close = 99.0 - (i - 3) * 0.8
            high = close + 0.3
            low = close - 0.4
        rows.append(Bar(ts, price, high, low, close, 1000.0))
        price = close
    return rows


def test_completed_bar_signal_is_directional_only():
    cfg = StrategyConfig(interval_minutes=5, opening_range_minutes=15)
    long_signal = generate_signal(_bars("LONG"), cfg)
    short_signal = generate_signal(_bars("SHORT"), cfg)
    assert long_signal.direction in {"LONG", "NONE"}
    assert short_signal.direction in {"SHORT", "NONE"}


def test_option_selection_never_crosses_direction():
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=7, min_option_volume=100, min_open_interest=100)
    contracts = [
        OptionContract("NIFTYCE", 100, "2026-08-20", "CE", 100, 99, 101, 75, 0.5, 10000, 20000),
        OptionContract("NIFTYPE", 100, "2026-08-20", "PE", 100, 99, 101, 75, -0.5, 10000, 20000),
    ]
    assert select_option(100, "LONG", contracts, cfg).option_type == "CE"
    assert select_option(100, "SHORT", contracts, cfg).option_type == "PE"


def test_trade_plan_is_lot_aligned_and_risk_bounded():
    cfg = StrategyConfig(max_risk_inr=3000, min_option_volume=100, min_open_interest=100)
    option = OptionContract("NIFTYCE", 100, "2026-08-20", "CE", 20, 19.5, 20.0, 75, 0.5, 10000, 20000)
    signal = Signal(
        direction="LONG",
        regime="TREND",
        timestamp=datetime(2026, 8, 19, 10, 0),
        or_high=100.0,
        or_low=99.0,
        vwap=100.5,
        atr=2.0,
        breakout_distance=1.0,
        volume_ratio=1.5,
        confidence=0.9,
        reason="test",
    )
    plan = build_trade_plan(signal, option, cfg, spot=101.0)
    assert plan.quantity % option.lot_size == 0
    assert plan.quantity >= 0
    assert plan.risk_inr <= cfg.max_risk_inr + 1e-9
