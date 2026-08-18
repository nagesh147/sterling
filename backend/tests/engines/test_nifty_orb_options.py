from datetime import datetime, timedelta, timezone

from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig, build_trade_plan, generate_signal, select_option, summarize_pnl

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


def test_long_breakout_requires_vwap_and_volume_alignment():
    signal = generate_signal(bars_for_breakout("LONG"), StrategyConfig())
    assert signal.direction == "LONG"
    assert signal.regime in {"TREND", "EXPANSION"}
    assert signal.confidence > 0


def test_option_selection_prefers_atm():
    contracts = [
        OptionContract("NIFTY", 23900, "2026-08-20", "CE", ltp=150, volume=1000, lot_size=65),
        OptionContract("NIFTY", 24000, "2026-08-20", "CE", ltp=110, volume=5000, lot_size=65),
        OptionContract("NIFTY", 24100, "2026-08-20", "CE", ltp=80, volume=2000, lot_size=65),
    ]
    chosen = select_option(24010, "LONG", contracts, StrategyConfig())
    assert chosen.strike == 24000


def test_trade_plan_respects_risk_cap():
    signal = generate_signal(bars_for_breakout("LONG"), StrategyConfig())
    option = OptionContract("NIFTY", 24000, "2026-08-20", "CE", ltp=110, lot_size=65, delta=0.5)
    plan = build_trade_plan(signal, option, StrategyConfig(max_risk_inr=3000), spot=24050)
    assert plan.quantity % 65 == 0
    assert plan.risk_inr <= 3000


def test_metrics_report_profit_factor_and_drawdown():
    metrics = summarize_pnl([100, -50, 200, -100])
    assert metrics["trades"] == 4
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown"] == 100
