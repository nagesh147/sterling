"""SuperTrend on the underlying, used as a direction gate.

The source names a corrective market cycle as the flaw that broke this strategy
and offers SuperTrend as the fix, without parameters. The parameters were
measured, and the obvious default turned out to be the trap:

    multiplier   period 7   period 10   period 14   period 21
       2.0         +7.0       +5.1        +6.5        +6.5
       2.5         +3.6       +3.3        +3.6        +3.6
       3.0         +1.3       -3.3        -1.6        -1.0
       4.0         +0.1       -0.7        -2.5        -3.3

(percentage-point lift in the MFE>=30% rate of trades where the gate agreed with
the trade's direction, against those where it disagreed.)

At multiplier 3.0 -- the conventional default -- the gate is *inverted* at three
of four periods: agreeing with it was worse than fighting it. At 2.0 the sign is
positive at every period. The default is 2.0 and the period is 10 only because
all four periods agree within noise and 10 is what the platform already uses;
picking period 7 for its +7.0 would be fitting the largest cell.

``unknown`` blocks. A gate that fails open is not a gate.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from app.engines.indicators.supertrend import compute_supertrend

from .config import GammaMoveConfig
from .models import Candle, OptionType, Regime


def regime_of(candles: Sequence[Candle], cfg: GammaMoveConfig) -> Regime:
    """Direction of the underlying, or ``unknown`` when it cannot be computed."""
    n = len(candles)
    if n < cfg.regime_period + 2:
        return "unknown"
    highs = np.array([c.high for c in candles], dtype=np.float64)
    lows = np.array([c.low for c in candles], dtype=np.float64)
    closes = np.array([c.close for c in candles], dtype=np.float64)
    try:
        _, trend = compute_supertrend(highs, lows, closes,
                                      cfg.regime_period, cfg.regime_multiplier)
    except Exception:                                              # noqa: BLE001
        return "unknown"
    last = int(trend[-1]) if len(trend) else 0
    return "up" if last > 0 else "down" if last < 0 else "unknown"


def regime_allows(regime: Regime, option_type: OptionType, cfg: GammaMoveConfig) -> bool:
    """Whether the gate permits this direction."""
    if not cfg.regime_enabled:
        return True
    if regime == "unknown":
        return False
    return (regime == "up") if option_type == "CE" else (regime == "down")


def regime_reason(regime: Regime, option_type: OptionType) -> str:
    if regime == "unknown":
        return "market direction is unreadable — not enough history for SuperTrend"
    want = "an uptrend" if option_type == "CE" else "a downtrend"
    return f"{option_type} needs {want}; SuperTrend says the trend is {regime}"
