"""Canonical ORB signal, option-selection and risk contract.

Every fixture here satisfies the *production* configuration. A gate is never
disabled to make a fixture pass: the bars are shaped so the gate under test is
the only unmet prerequisite.
"""
from datetime import date, datetime, timedelta, timezone

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
SESSION_OPEN = datetime(2026, 8, 18, 9, 15, tzinfo=IST)
OR_HIGH, OR_LOW = 24012.0, 23988.0


def _ts(index: int) -> datetime:
    return SESSION_OPEN + timedelta(minutes=5 * index)


def _bar(index: int, open_: float, close: float, volume: float, *, pad: float = 4.0) -> Bar:
    return Bar(_ts(index), open_, max(open_, close) + pad, min(open_, close) - pad, close, volume)


def _opening_range_bars() -> list[Bar]:
    """Three 09:15-09:30 bars establishing a 23988-24012 opening range."""
    return [Bar(_ts(i), 24000.0, OR_HIGH, OR_LOW, 24000.0, 1200) for i in range(3)]


def orb_session(direction: str = "LONG", *, bars: int = 30) -> list[Bar]:
    """A clean ORB day: opening range, quiet drift, then a break on rising volume.

    The final bar closes at 11:40 IST -- inside the default 09:30-12:00 entry
    window -- and satisfies every canonical predicate under ``StrategyConfig()``.
    Passing ``bars=40`` pushes the same break past 12:00.
    """
    rows = _opening_range_bars()
    price = 24000.0
    for i in range(3, bars):
        if i < bars - 5:
            close = price + (2.0 if i % 2 else -2.0)
            rows.append(_bar(i, price, close, 1000, pad=3.0))
        else:
            close = price + (18.0 if direction == "LONG" else -18.0)
            rows.append(_bar(i, price, close, 1000 + 500 * (i - (bars - 6))))
        price = close
    return rows


# --------------------------------------------------------------------------
# opening range
# --------------------------------------------------------------------------

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


def test_missing_opening_range_is_an_error_not_a_signal():
    late = [_bar(i, 24000.0 + i, 24001.0 + i, 1000) for i in range(6, 30)]
    with pytest.raises(ValueError, match="Opening range bars are missing"):
        generate_signal(late, StrategyConfig())


# --------------------------------------------------------------------------
# canonical signals under the production configuration
# --------------------------------------------------------------------------

def test_long_breakout_requires_vwap_and_volume_alignment():
    signal = generate_signal(orb_session("LONG"), StrategyConfig())
    assert signal.direction == "LONG"
    assert signal.regime in {"TREND", "EXPANSION"}
    assert signal.confidence > 0
    assert signal.breakout_distance >= StrategyConfig().min_breakout_atr * signal.atr
    assert signal.volume_ratio >= StrategyConfig().volume_multiplier


def test_short_breakout_maps_to_pe_signal():
    signal = generate_signal(orb_session("SHORT"), StrategyConfig())
    assert signal.direction == "SHORT"
    assert signal.reason.startswith("ORB low break")


# --------------------------------------------------------------------------
# one test per signal gate: exactly one prerequisite is unmet
# --------------------------------------------------------------------------

def test_gate_entry_window_blocks_a_late_breakout():
    signal = generate_signal(orb_session("LONG", bars=40), StrategyConfig())
    assert signal.timestamp.astimezone(IST).strftime("%H:%M") == "12:30"
    assert signal.direction == "NONE"
    assert signal.reason == "outside entry window"


def test_gate_requires_an_opening_range_breakout():
    rows = _opening_range_bars()
    price = 24000.0
    for i in range(3, 30):                      # drifts inside the range all day
        close = price + (2.0 if i % 2 else -2.0)
        rows.append(_bar(i, price, close, 1000 + 40 * i, pad=3.0))
        price = close
    signal = generate_signal(rows, StrategyConfig())
    assert signal.direction == "NONE"
    assert signal.reason == "no opening-range breakout"


def test_gate_requires_the_atr_scaled_breakout_threshold():
    bars = orb_session("LONG")
    baseline = generate_signal(bars, StrategyConfig())
    demanding = baseline.breakout_distance / baseline.atr * 1.5
    signal = generate_signal(bars, StrategyConfig(min_breakout_atr=demanding))
    assert signal.direction == "NONE"
    assert signal.reason == "breakout below ATR threshold"


def test_gate_requires_close_on_the_signal_side_of_vwap():
    """A heavy rally lifts VWAP above a later pullback that still clears the OR."""
    rows = _opening_range_bars()
    price = 24000.0
    for i in range(3, 14):
        price += 40.0
        rows.append(_bar(i, price - 40.0, price, 6000))
    for i in range(14, 26):
        price -= 30.0
        rows.append(_bar(i, price + 30.0, price, 900))
    signal = generate_signal(rows, StrategyConfig())
    assert signal.direction == "NONE"
    assert rows[-1].close > OR_HIGH and rows[-1].close < signal.vwap
    assert signal.reason == "close is not above VWAP"


def test_gate_requires_a_confirming_vwap_slope():
    """Heavy distribution then a heavy re-test: price rises while VWAP still falls."""
    rows = _opening_range_bars()
    price = 24000.0
    for _ in range(10):
        price += 40.0
        rows.append(_bar(len(rows), price - 40.0, price, 14000))
    for _ in range(4):
        price -= 120.0
        rows.append(_bar(len(rows), price + 120.0, price, 300))
    for _ in range(5):
        price += 35.0
        rows.append(_bar(len(rows), price - 35.0, price, 80000))
    signal = generate_signal(rows, StrategyConfig())
    assert signal.direction == "NONE"
    assert rows[-1].close > signal.vwap > 0
    assert signal.regime in {"TREND", "EXPANSION"}
    assert signal.reason == "VWAP slope is not positive"


def test_gate_requires_volume_confirmation():
    bars = orb_session("LONG")
    quiet = bars[:-1] + [Bar(bars[-1].timestamp, bars[-1].open, bars[-1].high, bars[-1].low, bars[-1].close, 100)]
    signal = generate_signal(quiet, StrategyConfig())
    assert signal.direction == "NONE"
    assert signal.volume_ratio < StrategyConfig().volume_multiplier
    assert signal.reason == "volume below confirmation threshold"


def test_gate_rejects_a_choppy_range_regime():
    rows = _opening_range_bars()
    price = 24000.0
    steps = [40, -30] * 11 + [42]
    for index, step in enumerate(steps):
        price += step
        last = index == len(steps) - 1
        rows.append(_bar(len(rows), price - step, price, 3000 if last else 1000))
    signal = generate_signal(rows, StrategyConfig())
    assert signal.direction == "NONE"
    assert signal.regime == "RANGE"
    assert signal.reason == "regime is RANGE"


def test_gate_ignores_a_still_forming_candle():
    bars = orb_session("LONG")
    closing_bar = bars[-1].timestamp
    # One minute before the 11:40 candle closes, the completed series ends at 11:35.
    signal = generate_signal(bars, StrategyConfig(), as_of=closing_bar + timedelta(minutes=4))
    assert signal.timestamp.astimezone(IST) == (closing_bar - timedelta(minutes=5)).astimezone(IST)
    assert generate_signal(bars, StrategyConfig(), as_of=closing_bar + timedelta(minutes=5)).timestamp == closing_bar


# --------------------------------------------------------------------------
# configuration validation: invalid values are errors, never bypasses
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"volume_multiplier": 0.0}, "volume_multiplier"),
        ({"volume_multiplier": -1.0}, "volume_multiplier"),
        ({"interval_minutes": 0}, "interval_minutes"),
        ({"opening_range_minutes": 0}, "opening_range_minutes"),
        ({"atr_period": 0}, "atr_period"),
        ({"vwap_slope_lookback": 0}, "vwap_slope_lookback"),
        ({"max_risk_inr": 0.0}, "max_risk_inr"),
        ({"max_trades_per_day": 0}, "max_trades_per_day"),
        ({"max_spread_pct": 0.0}, "max_spread_pct"),
        ({"min_breakout_atr": -0.1}, "min_breakout_atr"),
        ({"min_option_volume": -1.0}, "min_option_volume"),
        ({"min_open_interest": -1.0}, "min_open_interest"),
        ({"entry_start": "12:00", "entry_end": "09:30"}, "earlier than"),
        ({"entry_start": "not-a-time"}, "HH:MM"),
        ({"expiry_dte_min": -1}, "expiry_dte_min"),
        ({"expiry_dte_min": 5, "expiry_dte_max": 2}, "expiry_dte_max"),
        ({"expiry_selection": "fortnightly"}, "expiry_selection"),
        ({"option_moneyness": "DEEP"}, "option_moneyness"),
        ({"avoid_expiry_day": True, "expiry_dte_min": 0, "expiry_dte_max": 0}, "avoid_expiry_day"),
    ],
)
def test_invalid_configuration_is_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        StrategyConfig(**overrides).validate()


def test_zero_volume_multiplier_cannot_bypass_the_volume_gate():
    """The old zero value both disabled the filter and divided by zero."""
    with pytest.raises(ValueError, match="volume_multiplier"):
        generate_signal(orb_session("LONG"), StrategyConfig(volume_multiplier=0.0))


def test_production_defaults_are_valid():
    assert StrategyConfig().validate() == StrategyConfig()


# --------------------------------------------------------------------------
# option selection and risk
# --------------------------------------------------------------------------

TODAY = date(2026, 8, 20)
NEAR_EXPIRY = "2026-08-27"


def liquid_contract(symbol, strike, expiry, option_type, *, ltp=110, lot_size=65, delta=0.5, volume=5000, oi=50000):
    return OptionContract(
        symbol,
        strike,
        expiry,
        option_type,
        ltp=ltp,
        bid=109.5,
        ask=110.5,
        lot_size=lot_size,
        delta=delta,
        volume=volume,
        open_interest=oi,
    )


def test_option_selection_maps_long_to_ce_and_short_to_pe():
    contracts = [
        liquid_contract("NIFTY-CE", 24000, NEAR_EXPIRY, "CE"),
        liquid_contract("NIFTY-PE", 24000, NEAR_EXPIRY, "PE"),
    ]
    cfg = StrategyConfig()
    assert select_option(24010, "LONG", contracts, cfg, today=TODAY).option_type == "CE"
    assert select_option(24010, "SHORT", contracts, cfg, today=TODAY).option_type == "PE"


def test_option_selection_prefers_configured_itm_strike():
    contracts = [
        liquid_contract("NIFTY-24000-CE", 24000, NEAR_EXPIRY, "CE"),
        liquid_contract("NIFTY-23900-CE", 23900, NEAR_EXPIRY, "CE"),
        liquid_contract("NIFTY-24100-PE", 24100, NEAR_EXPIRY, "PE"),
    ]
    cfg = StrategyConfig(option_moneyness="ITM", option_steps_itm=1)
    assert select_option(24010, "LONG", contracts, cfg, today=TODAY).strike == 23900
    assert select_option(24010, "SHORT", contracts, cfg, today=TODAY).strike == 24100


def test_option_selection_rejects_illiquid_contracts():
    contracts = [liquid_contract("NIFTY-CE", 24000, NEAR_EXPIRY, "CE", volume=10)]
    with pytest.raises(ValueError, match="No liquid CE contracts"):
        select_option(24010, "LONG", contracts, StrategyConfig(), today=TODAY)


def test_trade_plan_respects_risk_cap():
    signal = generate_signal(orb_session("LONG"), StrategyConfig())
    assert signal.direction == "LONG"
    option = liquid_contract("NIFTY", 24000, NEAR_EXPIRY, "CE", delta=0.5)
    plan = build_trade_plan(signal, option, StrategyConfig(max_risk_inr=3000), spot=24050)
    assert plan.quantity % 65 == 0
    assert plan.risk_inr <= 3000
    assert plan.option_type == "CE"


def test_trade_plan_rejects_wrong_option_direction():
    signal = generate_signal(orb_session("LONG"), StrategyConfig())
    option = liquid_contract("NIFTY-PE", 24000, NEAR_EXPIRY, "PE")
    with pytest.raises(ValueError, match="Option direction"):
        build_trade_plan(signal, option, StrategyConfig(), spot=24050)


def test_metrics_report_profit_factor_and_drawdown():
    metrics = summarize_pnl([100, -50, 200, -100])
    assert metrics["trades"] == 4
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["max_drawdown"] == 100
