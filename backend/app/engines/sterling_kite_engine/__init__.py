"""Kite-exclusive 1H Heikin-Ashi Sterling Kite Engine options engine.

Broker/market-agnostic core: closed candles in, ``Signal``s out. Imports NO
strategy/signal/options/derivative logic from any other engine — only the shared
indicator primitives (``compute_heikin_ashi``, ``compute_supertrend``) and the
canonical ``app.domain.models.Signal`` schema.
"""
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.engine import (
    ManageResult,
    SterlingKiteEngine,
)
from app.engines.sterling_kite_engine.regime import (
    RegimeSeries,
    compute_regime,
    entry_transitions,
)

__all__ = [
    "SterlingKiteEngineConfig",
    "SterlingKiteEngine",
    "ManageResult",
    "compute_regime",
    "entry_transitions",
    "RegimeSeries",
]
