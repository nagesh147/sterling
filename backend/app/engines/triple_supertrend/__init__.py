"""Kite-exclusive 1H Heikin-Ashi triple-SuperTrend options engine.

Broker/market-agnostic core: closed candles in, ``Signal``s out. Imports NO
strategy/signal/options/derivative logic from any other engine — only the shared
indicator primitives (``compute_heikin_ashi``, ``compute_supertrend``) and the
canonical ``app.domain.models.Signal`` schema.
"""
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import (
    ManageResult,
    TripleSupertrendEngine,
)
from app.engines.triple_supertrend.regime import (
    RegimeSeries,
    compute_regime,
    entry_transitions,
)

__all__ = [
    "TripleSupertrendConfig",
    "TripleSupertrendEngine",
    "ManageResult",
    "compute_regime",
    "entry_transitions",
    "RegimeSeries",
]
