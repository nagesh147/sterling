"""Triple SuperTrend strategy — self-contained trend-following system.

A clean-seam strategy module built on the kept indicator/backtest/risk infra.
It is deliberately decoupled from the reset `directional/` stubs and the old
options-oriented schemas: everything it needs lives under this package.

Public surface
--------------
- `config`   : modes, asset-class tables, tunable `TripleSTConfig`
- `features` : one-shot indicator computation over a candle series
- `engine`   : per-bar evaluation (regime → consensus → quality → filters →
               sizing → exits) plus the live capital-protection state machine
- `backtest` : bar-by-bar historical replay (next-bar-open fills, slippage,
               exit-priority ladder, equity curve + stats)

The FastAPI surface lives in `app/api/v1/endpoints/strategy.py`.
"""
from app.engines.triple_st.config import (
    StrategyMode,
    AssetClass,
    MODE_TABLE,
    ASSET_TABLE,
    classify_asset,
    default_config,
)

__all__ = [
    "StrategyMode",
    "AssetClass",
    "MODE_TABLE",
    "ASSET_TABLE",
    "classify_asset",
    "default_config",
]
