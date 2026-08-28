"""OI Wall Flow -- buy the first-resistance CE (or first-support PE) the chain is writing.

An Indian F&O chain is not a list of prices. It is a map of where writers are
defending (call wall), where they are cushioning (put wall), and whether they
are covering or adding. When near-ATM calls are being covered and puts are
being written, the trade is the first OTM call at the call wall -- not ATM,
not a far lottery strike.

Motivated by the BSE Ltd 29-Sep-2026 chain (spot 3392.50, call wall 3500,
put wall 3300). See ``docs/strategy/oi-wall-flow/``.

This package is self-contained strategy mathematics: no broker, no socket, no
clock. Every other engine in this codebase is untouched by it.
"""
from __future__ import annotations

from .bias import decide
from .classify import classify_side, max_pain, measure, walls_of
from .config import JUDGEMENT, JUDGEMENT_FIELDS, OIWallFlowConfig
from .exits import realised_inr, should_exit
from .models import (BiasReport, ChainMetrics, ChainRow, ChainSnapshot, FlowLabel,
                     FlowSignal, InstrumentRef, PositionState, TradePlan,
                     TradeRecord, Walls, align_to_tick, q2)
from .selection import first_otm_call, first_otm_put, make_plan, pick_row
from .strategy import Decision, Intent, OIWallFlowStrategy, Phase, SessionState

STRATEGY_ID = "oi_wall_flow"
STRATEGY_NAME = "OI Wall Flow"
CONTRACT_VERSION = "A320.1"

__all__ = [
    "STRATEGY_ID", "STRATEGY_NAME", "CONTRACT_VERSION",
    "OIWallFlowConfig", "JUDGEMENT", "JUDGEMENT_FIELDS",
    "OIWallFlowStrategy", "SessionState", "Decision", "Intent", "Phase",
    "ChainRow", "ChainSnapshot", "ChainMetrics", "FlowLabel", "Walls",
    "BiasReport", "TradePlan", "FlowSignal", "InstrumentRef", "PositionState",
    "TradeRecord", "q2", "align_to_tick",
    "classify_side", "measure", "max_pain", "walls_of", "decide",
    "pick_row", "first_otm_call", "first_otm_put", "make_plan",
    "should_exit", "realised_inr",
]
