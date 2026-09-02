"""Bear to Bearish Strategy Engine — Momentum Short setup using Live PCR Movement & Price Action.

Monitors intraday Put-Call Ratio (PCR < 0.60, steady PCR decline) combined with Lower High (LH)
price action structure on 1m/3m/5m timeframe. Triggers auto-execution short orders via OrderRouter.
"""
from app.engines.bear_to_bearish.models import (
    BearToBearishConfig,
    BearToBearishSignal,
    BearToBearishSnapshot,
    PcrPoint,
)
from app.engines.bear_to_bearish.strategy import evaluate_bear_to_bearish

__all__ = [
    "BearToBearishConfig",
    "BearToBearishSignal",
    "BearToBearishSnapshot",
    "PcrPoint",
    "evaluate_bear_to_bearish",
]
