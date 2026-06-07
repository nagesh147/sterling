"""Mean-reversion sleeve — SCAFFOLD, DISABLED.

The honest 2026-06-07 walk-forward validation (study/mean_reversion_wf.py)
found higher-timeframe (2h/4h) Bollinger+RSI mean-reversion to be the ONE real
edge candidate in the system: positive out-of-sample, beats buy-and-hold, and
generalises to symbols never used in selection — but with too few trades to
clear deflation (DSR ~0.01-0.04, far below the 0.5 bar).

So this module holds the strategy READY but UNWIRED:
  * It is NOT in `edge.strategies.SIGNAL_FNS` and NOT in any live registry.
  * The live `EdgeGate` (registry.EdgeGate.min_dsr = 0.5) is the bouncer — even
    if accidentally wired, it cannot emit live signals below DSR 0.5.
  * Promotion criterion: re-validate on a multi-symbol basket
    (docs/mean_reversion_sleeve_plan.md) and only then flip `QUALIFIED`, set the
    validated params, and register it. Never automatic.

`SLEEVE_PARAMS` are the most-selected walk-forward parameters — defensive
defaults for further research, NOT a deployment recommendation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Most-selected anchored-walk-forward parameters on BTC 4h (BB lookback, BB std
# multiplier, RSI period, RSI oversold threshold).
SLEEVE_PARAMS = {"bb_lookback": 30, "bb_std": 2.5, "rsi_period": 14, "rsi_threshold": 30}
SLEEVE_PROFILE = "Intraday"          # (sl_mult, tp_mult) via registry.PROFILE_CONFIG
QUALIFY_DSR = 0.5                    # deflated-Sharpe bar required to go live
QUALIFIED = False                   # flip ONLY after multi-symbol validation


def signals(df: pd.DataFrame, *, bb_lookback: int | None = None,
            bb_std: float | None = None, rsi_period: int | None = None,
            rsi_threshold: float | None = None) -> np.ndarray:
    """Long-only mean-reversion: buy when price reclaims the lower Bollinger band
    while RSI is oversold. Same family as `edge.strategies` bb_rsi but
    parameterised. Uses only past data (.shift) — no lookahead. Returns a bool
    array aligned to `df`."""
    p = SLEEVE_PARAMS
    bb_lookback = bb_lookback or p["bb_lookback"]
    bb_std = bb_std if bb_std is not None else p["bb_std"]
    rsi_period = rsi_period or p["rsi_period"]
    rsi_threshold = rsi_threshold if rsi_threshold is not None else p["rsi_threshold"]
    c = df["close"]
    d = c.diff()
    gain = d.clip(lower=0).rolling(rsi_period).mean()
    loss = (-d.clip(upper=0)).rolling(rsi_period).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    sma = c.rolling(bb_lookback).mean()
    std = c.rolling(bb_lookback).std()
    lower = sma - bb_std * std
    reclaim = (c > lower) & (c.shift(1) <= lower.shift(1))
    return (reclaim & (rsi < rsi_threshold)).fillna(False).to_numpy()


def is_qualified(dsr: float) -> bool:
    """A config may be wired live only at/above the deflation bar. This is the
    single gate the promotion procedure (and any future automation) must call."""
    return dsr >= QUALIFY_DSR
