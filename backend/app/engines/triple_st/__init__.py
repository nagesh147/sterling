"""Daily SMA/EMA + RSI/ADX strategy — self-contained, long+short.

A clean, minimal strategy module built on the kept indicator/backtest infra.

Rule (1D timeframe)
-------------------
    Long  entry : close > SMA(50) and close > EMA(7) and RSI(2) > ADX(2)
    Long  exit  : RSI(2) < ADX(2)
    Short entry : close < SMA(50) and close < EMA(7) and RSI(2) < ADX(2)
    Short exit  : RSI(2) > ADX(2)

Public surface
--------------
- `config`   : tunable `TripleSTConfig` (periods, direction toggles, risk)
- `features` : daily-candle indicator computation + 1H→1D resampling
- `engine`   : per-bar signal evaluation + risk-based trade plan
- `backtest` : bar-by-bar historical replay + live evaluation snapshot

The FastAPI surface lives in `app/api/v1/endpoints/strategy.py`.
"""
from app.engines.triple_st.config import TripleSTConfig, default_config

__all__ = ["TripleSTConfig", "default_config"]
