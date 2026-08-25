"""Unit tests for the Smart Money Multi-X Options strategy engine."""
import pytest
from app.engines.smart_money_options import (
    Candle,
    SmartMoneyOptionsConfig,
    SignalAction,
    StructurePhase,
    analyze_market_structure,
    analyze_smart_money_volume,
    resolve_option_strike,
    evaluate_smart_money_strategy,
)


def test_market_structure_consolidation_and_breakout():
    # 10 candles in tight consolidation
    candles = [
        Candle(timestamp_ms=i * 86400000, open=100.0, high=102.0, low=98.0, close=100.5, volume=1000.0)
        for i in range(10)
    ]
    struct = analyze_market_structure("TEST", candles, min_consolidation_bars=8, max_range_pct=8.0)
    assert struct.phase == StructurePhase.CONSOLIDATION
    assert struct.is_compressed is True
    assert struct.resistance == 102.0
    assert struct.support == 98.0

    # Add breakout candle closing above 102.0
    breakout_candle = Candle(timestamp_ms=11 * 86400000, open=101.0, high=106.0, low=100.8, close=105.5, volume=5000.0)
    struct_bo = analyze_market_structure("TEST", candles + [breakout_candle], min_consolidation_bars=8, max_range_pct=8.0)
    assert struct_bo.phase == StructurePhase.BREAKOUT_CONFIRMED


def test_smart_money_volume_analysis():
    # Normal volume candles
    candles = [
        Candle(timestamp_ms=i * 3600000, open=100.0, high=101.0, low=99.0, close=100.2, volume=10000.0)
        for i in range(20)
    ]
    # Add high volume bullish candle closing at high
    surge_candle = Candle(
        timestamp_ms=21 * 3600000,
        open=100.5,
        high=105.0,
        low=100.2,
        close=104.8,
        volume=25000.0,  # 2.5x volume!
    )
    metrics = analyze_smart_money_volume(candles + [surge_candle], volume_surge_multiplier=1.8)
    assert metrics.rvol >= 2.0
    assert metrics.delta_pressure > 0.5
    assert metrics.is_institutional_surge is True
    assert metrics.footprint_score > 70.0


def test_option_strike_selection():
    # ABB at 6850 spot
    strike_ce = resolve_option_strike("ABB", 6850.0, "CE", policy="OTM1")
    assert strike_ce == 7000.0  # ATM is 6900 + 100 step = 7000 CE (matches video!)

    strike_atm = resolve_option_strike("ABB", 6850.0, "CE", policy="ATM")
    assert strike_atm == 6900.0

    strike_pe = resolve_option_strike("ABB", 6850.0, "PE", policy="OTM1")
    assert strike_pe == 6800.0


def test_full_strategy_breakout_multi_x_targets():
    config = SmartMoneyOptionsConfig(
        enabled=True,
        min_consolidation_bars=8,
        volume_surge_multiplier=1.8,
        target_multiplier_1=2.0,
        target_multiplier_2=3.0,
        target_multiplier_3=5.0,
        stop_loss_pct=35.0,
    )

    # Base candles in consolidation
    htf = [
        Candle(timestamp_ms=i * 86400000, open=7000.0, high=7050.0, low=6950.0, close=7010.0, volume=50000.0)
        for i in range(15)
    ]
    # Breakout candle closing above 7050 with huge volume
    htf_breakout = Candle(
        timestamp_ms=16 * 86400000,
        open=7020.0,
        high=7180.0,
        low=7010.0,
        close=7170.0,
        volume=180000.0,
    )

    ltf = [
        Candle(timestamp_ms=i * 3600000, open=7000.0, high=7030.0, low=6980.0, close=7010.0, volume=10000.0)
        for i in range(20)
    ]
    ltf_breakout = Candle(
        timestamp_ms=21 * 3600000,
        open=7020.0,
        high=7180.0,
        low=7010.0,
        close=7170.0,
        volume=35000.0,
    )

    sig = evaluate_smart_money_strategy(
        symbol="ABB",
        htf_candles=htf + [htf_breakout],
        ltf_candles=ltf + [ltf_breakout],
        config=config,
        option_quote_premium=220.0,  # 220 entry premium from video!
    )

    assert sig.action == SignalAction.BUY_CE
    assert sig.status == "armed"
    assert sig.option_type == "CE"
    assert sig.entry_premium == 220.0
    assert sig.targets is not None
    assert sig.targets.target_1_2x == 440.0   # 2X (220 * 2)
    assert sig.targets.target_2_3x == 660.0   # 3X (220 * 3)
    assert sig.targets.target_3_5x == 1100.0  # 5X (220 * 5)
    assert sig.stop_loss_premium == 143.0     # 35% SL (220 * 0.65)
