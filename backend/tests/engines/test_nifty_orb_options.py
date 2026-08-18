from datetime import datetime, timedelta, timezone

from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig, build_trade_plan, generate_signal, opening_range, select_option, summarize_pnl

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


def test_option_selection_maps_long_to_ce_and_short_to_pe():
    contracts = [
        OptionContract("NIFTY-CE", 24000, "2026-08-20", "CE", ltp=110, volume=5000, lot_size=65),
        OptionContract("NIFTY-PE", 24000, "2026-08-20", "PE", ltp=110, volume=5000, lot_size=65),
    ]
    cfg = StrategyConfig()
    assert select_option(24010, "LONG", contracts, cfg).option_type == "CE"
    assert select_option(24010, "SHORT", contracts, cfg).option_type == "PE"


def test_trade_plan_respects_risk_cap():
    signal = generate_signal(bars_for_breakout("LONG"), StrategyConfig())
    option = OptionContract("NIFTY", 24000, "2026-08-20", "CE", ltp=110, lot_size=65, delta=0.5)
    plan = build_trade_plan(signal, option, StrategyConfig(max_risk_inr=3000), spot=24050)
    assert plan.quantity % 65 == 0
    assert plan.risk_inr <= 3000
    assert plan.option_type == "CE"


def test_metrics_report_profit_factor_and_drawdown():
    metrics = summarize_pnl([100, -50, 200, -100])
    assert metrics["trades"] == 4
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown"] == 100
