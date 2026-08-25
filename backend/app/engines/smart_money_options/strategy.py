"""Core strategy orchestrator for Smart Money Structure & Multi-X Options."""
from __future__ import annotations

from typing import Optional, Sequence
from app.engines.smart_money_options.config import SmartMoneyOptionsConfig
from app.engines.smart_money_options.models import (
    BreakoutSignal,
    Candle,
    MultiXTarget,
    SignalAction,
    StructurePhase,
)
from app.engines.smart_money_options.selection import resolve_option_strike
from app.engines.smart_money_options.smart_money import analyze_smart_money_volume
from app.engines.smart_money_options.structure import analyze_market_structure


def evaluate_smart_money_strategy(
    symbol: str,
    htf_candles: Sequence[Candle],
    ltf_candles: Sequence[Candle],
    config: SmartMoneyOptionsConfig,
    option_quote_premium: Optional[float] = None,
    expiry_str: Optional[str] = None,
    tradingsymbol: Optional[str] = None,
) -> BreakoutSignal:
    """Evaluate HTF structure and LTF Smart Money footprint to generate Multi-X signals."""
    if not htf_candles or not ltf_candles:
        return BreakoutSignal(
            symbol=symbol,
            action=SignalAction.NO_TRADE,
            spot_price=0.0,
            reason="Insufficient candle data",
            status="watching",
        )

    current_spot = ltf_candles[-1].close
    timestamp_ms = ltf_candles[-1].timestamp_ms

    # 1. Higher-timeframe base structure & liquidity levels
    htf_struct = analyze_market_structure(
        symbol=symbol,
        candles=htf_candles,
        timeframe=config.htf_timeframe,
        min_consolidation_bars=config.min_consolidation_bars,
        max_range_pct=config.max_consolidation_range_pct,
    )

    # 2. Lower-timeframe volume surge and institutional footprint
    sm_metrics = analyze_smart_money_volume(
        candles=ltf_candles,
        volume_surge_multiplier=config.volume_surge_multiplier,
    )

    # 3. Breakout evaluation
    is_footprint_valid = (
        sm_metrics.is_institutional_surge or sm_metrics.footprint_score >= config.min_footprint_score
    )

    # Bullish condition: breaking resistance with aggressive buying footprint
    bullish_breakout = (
        current_spot >= htf_struct.resistance * 0.998
        and sm_metrics.delta_pressure > 0.25
        and is_footprint_valid
    )

    # Bearish condition: breaking support with aggressive selling footprint
    bearish_breakdown = (
        current_spot <= htf_struct.support * 1.002
        and sm_metrics.delta_pressure < -0.25
        and is_footprint_valid
    )

    if not bullish_breakout and not bearish_breakdown:
        phase_desc = (
            f"Consolidating in {htf_struct.range_pct}% range [{htf_struct.support:.1f} - {htf_struct.resistance:.1f}]"
            if htf_struct.phase == StructurePhase.CONSOLIDATION
            else f"Market phase: {htf_struct.phase.value}"
        )
        return BreakoutSignal(
            symbol=symbol,
            action=SignalAction.NO_TRADE,
            spot_price=current_spot,
            structure_phase=htf_struct.phase,
            rvol=sm_metrics.rvol,
            footprint_score=sm_metrics.footprint_score,
            reason=f"No breakout trigger. {phase_desc}. RVOL: {sm_metrics.rvol}x",
            timestamp_ms=timestamp_ms,
            status="watching",
        )

    # Setup triggered: Choose option parameters
    option_type = "CE" if bullish_breakout else "PE"
    action = SignalAction.BUY_CE if bullish_breakout else SignalAction.BUY_PE
    strike = resolve_option_strike(
        symbol=symbol,
        spot_price=current_spot,
        option_type=option_type,
        policy=config.strike_selection,
    )

    # Estimate entry premium if live quote not passed (typically ~2.5% of spot for OTM1 near monthly)
    entry_premium = option_quote_premium or round(current_spot * 0.028, 2)
    entry_premium = max(entry_premium, 1.0)

    # Calculate Multi-X Targets
    t1 = entry_premium * config.target_multiplier_1
    t2 = entry_premium * config.target_multiplier_2
    t3 = entry_premium * config.target_multiplier_3
    targets = MultiXTarget(
        target_1_2x=t1,
        target_2_3x=t2,
        target_3_5x=t3,
    )

    # Calculate Stop Loss
    sl_prem = max(0.5, entry_premium * (1.0 - config.stop_loss_pct / 100.0))
    sl_spot = htf_struct.support if bullish_breakout else htf_struct.resistance

    confidence = min(0.95, 0.5 + (sm_metrics.footprint_score / 200.0) + (0.1 if htf_struct.is_compressed else 0.0))

    direction_label = "Bullish BSL Breakout" if bullish_breakout else "Bearish SSL Breakdown"
    reason = (
        f"{direction_label} confirmed on {config.ltf_timeframe} with Smart Money volume {sm_metrics.rvol}x "
        f"(Footprint score: {sm_metrics.footprint_score}). Target Multi-X: 2X/3X/5X."
    )

    return BreakoutSignal(
        symbol=symbol,
        action=action,
        spot_price=current_spot,
        option_type=option_type,
        strike=strike,
        expiry=expiry_str,
        tradingsymbol=tradingsymbol or f"{symbol} {strike:g} {option_type}",
        entry_premium=round(entry_premium, 2),
        stop_loss_premium=round(sl_prem, 2),
        stop_loss_spot=round(sl_spot, 2),
        targets=targets,
        holding_period_days=config.holding_period_days,
        rvol=sm_metrics.rvol,
        footprint_score=sm_metrics.footprint_score,
        structure_phase=StructurePhase.BREAKOUT_CONFIRMED,
        reason=reason,
        confidence=round(confidence, 2),
        timestamp_ms=timestamp_ms,
        status="armed",
    )
