"""Smart Money Structure & Multi-X Options strategy engine.

Implements the institutional market structure breakout framework:
1. Higher-timeframe base / consolidation identification & liquidity mapping (SSL/BSL).
2. Lower-timeframe structural breakout + Smart Money volume surge (RVOL / Footprint).
3. Call / Put option selection (OTM1/OTM2/ATM).
4. Multi-X target scaling (2X, 3X, 5X) with structural stop loss and 5-day swing horizon.
"""
from __future__ import annotations

STRATEGY_ID = "smart_money_options"
STRATEGY_NAME = "Smart Money Multi-X Options"
CONTRACT_VERSION = "SMX.1.0"

from app.engines.smart_money_options.config import (
    SmartMoneyOptionsConfig,
    StrikeSelectionPolicy,
    ExpiryPolicy,
    ExecutionMode,
)
from app.engines.smart_money_options.models import (
    Candle,
    MarketStructure,
    LiquidityLevel,
    SmartMoneyMetrics,
    SmartMoneySetup,
    BreakoutSignal,
    MultiXTarget,
    SignalAction,
    StructurePhase,
)
from app.engines.smart_money_options.structure import analyze_market_structure
from app.engines.smart_money_options.smart_money import analyze_smart_money_volume
from app.engines.smart_money_options.selection import resolve_option_strike
from app.engines.smart_money_options.strategy import evaluate_smart_money_strategy

__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "CONTRACT_VERSION",
    "SmartMoneyOptionsConfig",
    "StrikeSelectionPolicy",
    "ExpiryPolicy",
    "ExecutionMode",
    "Candle",
    "MarketStructure",
    "LiquidityLevel",
    "SmartMoneyMetrics",
    "SmartMoneySetup",
    "BreakoutSignal",
    "MultiXTarget",
    "SignalAction",
    "StructurePhase",
    "analyze_market_structure",
    "analyze_smart_money_volume",
    "resolve_option_strike",
    "evaluate_smart_money_strategy",
]
