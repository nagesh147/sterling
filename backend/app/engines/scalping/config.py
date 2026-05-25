"""Configuration for the 4H+15min scalping strategies.

All three strategies (Price Action, SMC, MA Crossover) share the same risk
and timeframe config. Each can be independently enabled/disabled.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ScalpingConfig(BaseModel):
    """Operator-facing config for the scalping module."""

    # ── Strategy toggles ──
    enable_price_action: bool = True
    enable_smc: bool = True
    enable_ma_crossover: bool = True

    # ── Timeframes ──
    structure_tf: str = "4h"       # 4H for support/resistance
    entry_tf: str = "15m"          # 15min for entry signals

    # ── 4H level detection ──
    level_touches: int = Field(default=2, ge=2, le=10, description="Min touches to qualify a level")
    level_tolerance_pct: float = Field(default=0.5, ge=0.1, le=3.0, description="% tolerance around level")

    # ── Price Action (Strategy 1) ──
    pa_lookback: int = Field(default=20, ge=5, le=100, description="15min bars for pattern detection")
    pa_breakout_pct: float = Field(default=0.1, ge=0.01, le=1.0, description="% beyond neckline for breakout confirm")

    # ── SMC (Strategy 2) ──
    smc_imbalance_ratio: float = Field(default=1.2, ge=1.0, le=3.0, description="Imbalance candle body / prev candle range min ratio")

    # ── MA Crossover (Strategy 3) ──
    ma_fast_period: int = Field(default=5, ge=2, le=20)
    ma_slow_period: int = Field(default=9, ge=3, le=50)

    # ── Direction toggles ──
    allow_long: bool = True
    allow_short: bool = True

    # ── Risk & sizing ──
    risk_percent: float = Field(default=1.0, ge=0.05, le=5.0)
    max_position_pct: float = Field(default=15.0, ge=1.0, le=100.0)
    account_equity: float = Field(default=100_000.0, gt=0)

    # ── Scanner scope ──
    symbols: List[str] = Field(default_factory=list, description="Empty = scan all stored coins")

    # ── Warmup ──
    warmup_bars_4h: int = Field(default=50, ge=20, le=200, description="Min 4H bars before first signal")
    warmup_bars_15m: int = Field(default=60, ge=20, le=300, description="Min 15min bars before first signal")


def default_config() -> ScalpingConfig:
    return ScalpingConfig()