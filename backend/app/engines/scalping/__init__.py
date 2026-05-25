"""Scalping strategies — 4H structure + 15min entry confirmation.

Three independent strategies sharing a common 4H support/resistance detector:

  1. Price Action   — chart patterns after 4H level test
  2. SMC            — inducement + imbalance candle after 4H liquidity zone test
  3. MA Crossover   — SMA(5) × EMA(9) crossover near 4H levels

Public surface
--------------
- `config`  : ScalpingConfig — enable/disable each strategy, risk params
- `levels`  : detect support/resistance on 4H candles
- `price_action` : Strategy 1 detector
- `smc`          : Strategy 2 detector
- `ma_crossover` : Strategy 3 detector
- `scanner`      : multi-symbol scan orchestrator
"""
from app.engines.scalping.config import ScalpingConfig, default_config

__all__ = ["ScalpingConfig", "default_config"]