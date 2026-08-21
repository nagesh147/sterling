"""ATM Premium Imbalance -- buy the cheaper ATM leg at the open, take +15 points.

Reconstructed from recordings of a third-party bot. See
``docs/strategy/atm-premium-imbalance/`` for the contract (A230), the evidence
behind every rule (A231) and the provenance of every default (A232).

This package is self-contained strategy mathematics: no broker, no socket, no
clock. Adaptive Edge is untouched by it.
"""
from __future__ import annotations

from .config import ATMPremiumImbalanceConfig
from .entry import EntryEngine, ManualPriceTable, PricedEntry, price_entry
from .exit import build_exit_event, exit_order_price, should_exit, stop_price, target_price
from .models import (
    ExitEvent,
    InstrumentRef,
    LegQuote,
    OptionPairRef,
    OrderReport,
    OrderStatus,
    PositionState,
    PremiumPairView,
    PremiumSignal,
    ReconcileState,
    TradeRecord,
    align_to_tick,
    q2,
)
from .quote_cache import PremiumQuoteCache
from .selection import resolve_pair, select_atm_strike, select_expiry
from .signal import evaluate, format_difference_line
from .strategy import ATMPremiumImbalanceStrategy, Intent, Phase

STRATEGY_ID = "atm_premium_imbalance"
STRATEGY_NAME = "ATM Premium Imbalance"
CONTRACT_VERSION = "A230.3"

__all__ = [
    "STRATEGY_ID", "STRATEGY_NAME", "CONTRACT_VERSION",
    "ATMPremiumImbalanceConfig", "ATMPremiumImbalanceStrategy", "Intent", "Phase",
    "PremiumQuoteCache", "PremiumPairView", "PremiumSignal", "evaluate", "format_difference_line",
    "EntryEngine", "ManualPriceTable", "PricedEntry", "price_entry",
    "target_price", "stop_price", "should_exit", "exit_order_price", "build_exit_event",
    "InstrumentRef", "OptionPairRef", "LegQuote", "OrderReport", "OrderStatus",
    "PositionState", "ReconcileState", "TradeRecord", "ExitEvent", "q2", "align_to_tick",
    "select_expiry", "select_atm_strike", "resolve_pair",
]
