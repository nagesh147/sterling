"""Market structure and liquidity pool analysis."""
from __future__ import annotations

from typing import Sequence
from app.engines.smart_money_options.models import (
    Candle,
    MarketStructure,
    StructurePhase,
)


def analyze_market_structure(
    symbol: str,
    candles: Sequence[Candle],
    timeframe: str = "1d",
    min_consolidation_bars: int = 8,
    max_range_pct: float = 8.0,
) -> MarketStructure:
    """Analyze higher-timeframe market structure to identify consolidation and liquidity pools."""
    if len(candles) < min_consolidation_bars:
        latest = candles[-1].close if candles else 0.0
        return MarketStructure(
            symbol=symbol,
            timeframe=timeframe,
            phase=StructurePhase.CHOPPY,
            resistance=latest,
            support=latest,
            range_pct=0.0,
            swing_high=latest,
            swing_low=latest,
            consolidation_bars=0,
            is_compressed=False,
        )

    # Use the prior window of bars to evaluate base/consolidation
    base_window = candles[:-1][-min_consolidation_bars:] if len(candles) > min_consolidation_bars else candles[-min_consolidation_bars:]
    highs = [c.high for c in base_window]
    lows = [c.low for c in base_window]
    closes = [c.close for c in base_window]

    swing_high = max(highs)
    swing_low = min(lows)
    current_close = candles[-1].close

    midpoint = (swing_high + swing_low) / 2.0 if (swing_high + swing_low) > 0 else 1.0
    range_pct = ((swing_high - swing_low) / midpoint) * 100.0

    # Calculate average bar range for compression detection
    bar_ranges = [c.high - c.low for c in base_window]
    avg_bar_range = sum(bar_ranges) / len(bar_ranges) if bar_ranges else 0.0
    recent_range = (candles[-1].high - candles[-1].low)
    is_compressed = range_pct <= max_range_pct and (recent_range <= avg_bar_range * 1.5)

    # Determine Phase
    if range_pct <= max_range_pct:
        # Check if latest candle is breaking out of the consolidation range
        if current_close > swing_high:
            phase = StructurePhase.BREAKOUT_CONFIRMED
        elif current_close >= swing_high * 0.995:
            phase = StructurePhase.BREAKOUT_IMMINENT
        elif current_close < swing_low:
            phase = StructurePhase.BREAKOUT_CONFIRMED
        elif current_close <= swing_low * 1.005:
            phase = StructurePhase.BREAKOUT_IMMINENT
        else:
            phase = StructurePhase.CONSOLIDATION
    else:
        # Range is broader - check trending vs choppy
        # Simple trend check: slope of closes
        first_close = closes[0]
        if current_close > first_close * 1.03:
            phase = StructurePhase.TRENDING
        elif current_close < first_close * 0.97:
            phase = StructurePhase.TRENDING
        else:
            phase = StructurePhase.CHOPPY

    return MarketStructure(
        symbol=symbol,
        timeframe=timeframe,
        phase=phase,
        resistance=round(swing_high, 2),
        support=round(swing_low, 2),
        range_pct=round(range_pct, 2),
        swing_high=round(swing_high, 2),
        swing_low=round(swing_low, 2),
        consolidation_bars=min_consolidation_bars,
        is_compressed=is_compressed,
    )
