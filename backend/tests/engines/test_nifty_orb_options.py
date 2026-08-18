from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import (
    Bar,
    OptionContract,
    StrategyConfig,
    build_trade_plan,
    generate_signal,
    opening_range,
    select_option,
    summarize_pnl,
)

IST = timezone(timedelta(hours=5, minutes=30))


def bars_for_breakout(direction="LONG"):
    day = datetime(2026, 8, 18, 9, 15, tzinfo=IST)
    rows = []
    price = 24000.0
    for i in range(40):
        ts = day + timedelta(minutes=5 * i)
        if i < 3:
            o, h, l, c = price, price + 10, price - 10, price + 2
        else:
            o = price
            if direction == "LONG":
                h, l, c = price + 8, price - 2, price + 6
            else:
                h, l, c = price + 2, price - 8, price - 6
        rows.append(Bar(ts, o, h, l, c, 1000 if i < 3 else 2500))
        price = c
    return rows


def liquid_contract(symbol, strike, expiry, option_type, *, ltp=110, lot_size=65, delta=0.5, volume=5000, oi=50000):
    return OptionContract(
        symbol,
        strike,
        expiry,
        option_type,
        ltp=ltp,
        bid=109,
        ask=110,
        lot_size=lot_size,
        delta=delta,
        volume=volume,
        open_interest=oi,
    )


def test_opening_range_uses_latest_session():
    previous = [
        Bar(datetime(2026, 8, 17, 9, 15, tzinfo=IST), 100, 105, 99, 104, 1000),
        Bar(datetime(2026, 8, 17, 9, 20, tzinfo=IST), 104, 106, 103, 105, 1000),
    ]
    current = [
        Bar(datetime(2026, 8, 18, 9, 15, tzinfo=IST), 200, 205, 198, 203, 1000),
        Bar(datetime(2026, 8, 18, 9, 20, tzinfo=IST), 203, 208, 201, 207, 1000),
        Bar(datetime(2026, 8, 18, 9, 25, tzinfo=IST), 207, 210, 206, 209, 1000),
    ]
    assert opening_range(previous + current, 15) == (210, 198)


def test_long_breakout_requires_vwap_and_volume_alignment():
    signal = generate_signal(bars_for_breakout("LONG"), StrategyConfig())
    assert signal.direction == "LONG"
    assert signal.regime in {"TREND", "EXPANSION"}
    assert signal.confidence > 0


def test_short_breakout_maps_to_pe_signal():
    signal = generate_signal(bars_for_breakout("SHORT"), StrategyConfig())
    assert signal.direction == "SHORT"
    assert signal.reason.startswith("ORB low break")


def test_signal_is_blocked_outside_entry_window():
    bars = bars_for_breakout("LONG")
    shifted = [Bar(b.timestamp.replace(hour=13, minute=b.timestamp.minute), b.open, b.high, b.low, b.close, b.volume) for b in bars]
    signal = generate_signal(shifted, StrategyConfig())
    assert signal.direction == "NONE"
    assert signal.reason == "outside entry window"


def test_option_selection_maps_long_to_ce_and_short_to_pe():
    contracts = [
        liquid_contract("NIFTY-CE", 24000, "2026-08-20", "CE"),
        liquid_contract("NIFTY-PE", 24000, "2026-08-20", "PE"),
    ]
    cfg = StrategyConfig()
    assert select_option(24010, "LONG", contracts, cfg).option_type == "CE"
    assert select_option(24010, "SHORT", contracts, cfg).option_type == "PE"


def test_option_selection_prefers_configured_itm_strike():
    contracts = [
        liquid_contract("NIFTY-24000-CE", 24000, "2026-08-20", "CE"),
        liquid_contract("NIFTY-23900-CE", 23900, "2026-08-20", "CE"),
        liquid_contract("NIFTY-24100-PE", 24100, "2026-08-20", "PE"),
    ]
    cfg = StrategyConfig(option_moneyness="ITM", option_steps_itm=1)
    assert select_option(24010, "LONG", contracts, cfg).strike == 23900
    assert select_option(24010, "SHORT", contracts, cfg).strike == 24100


def test_option_selection_rejects_illiquid_contracts():
    contracts = [liquid_contract("NIFTY-CE", 24000, "2026-08-20", "CE", volume=10)]
    with pytest.raises(ValueError, match="No liquid CE contracts"):
        select_option(24010, "LONG", contracts, StrategyConfig())


def test_trade_plan_respects_risk_cap():
    signal = generate_signal(bars_for_breakout("LONG"), StrategyConfig())
    option = liquid_contract("NIFTY", 24000, "2026-08-20", "CE", delta=0.5)
    plan = build_trade_plan(signal, option, StrategyConfig(max_risk_inr=3000), spot=24050)
    assert plan.quantity % 65 == 0
    assert plan.risk_inr <= 3000
    assert plan.option_type == "CE"


def test_trade_plan_rejects_wrong_option_direction():
    signal = generate_signal(bars_for_breakout("LONG"), StrategyConfig())
    option = liquid_contract("NIFTY-PE", 24000, "2026-08-20", "PE")
    with pytest.raises(ValueError, match="Option direction"):
        build_trade_plan(signal, option, StrategyConfig(), spot=24050)


def test_metrics_report_profit_factor_and_drawdown():
    metrics = summarize_pnl([100, -50, 200, -100])
    assert metrics["trades"] == 4
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown"] == 100
