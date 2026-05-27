"""Configuration for the 4H+15min scalping strategies.

All three strategies (Price Action, SMC, MA Crossover) share the same risk
and timeframe config. Each can be independently enabled/disabled.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class TieredTPConfig(BaseModel):
    """Tiered take-profit configuration for scalping positions.

    When price reaches tp1_r_multiple × risk_distance, a fractional
    clip is closed and the remaining stop is pulled to breakeven.
    """

    enabled: bool = Field(default=True, description="Enable tiered scale-out on scalping positions")
    tp1_r_multiple: float = Field(default=1.5, ge=0.5, le=10.0, description="R-multiple to trigger first scale-out")
    tp1_size_pct: float = Field(default=0.30, ge=0.10, le=0.75, description="Fraction of position to close at TP1")
    move_to_be_at_tp1: bool = Field(default=True, description="Pull remaining stop to entry when TP1 hits")


class EngineConfig(BaseModel):
    """Operator-facing config for the scalping module."""

    # Timeframe Controls
    execution_timeframe: str = "15m"
    macro_timeframe: str = "4h"

    # ── Strategy toggles ──
    enable_price_action: bool = True
    enable_smc: bool = True
    enable_ma_crossover: bool = True

    # ── 4H level detection ──
    level_touches: int = Field(default=2, ge=2, le=10, description="Min touches to qualify a level")
    level_tolerance_pct: float = Field(default=0.5, ge=0.1, le=3.0, description="% tolerance around level")

    # Strategy 1: Price Action Settings
    pa_lookback_bars: int = 30
    pa_min_pivot_distance: int = 5       # Minimum bars between peaks/valleys
    pa_max_bottom_variance: float = 0.01  # Max 1% variance between bottom 1 and 2
    pa_min_neckline_height: float = 0.01  # Neckline must be >= 1% above bottoms

    # Strategy 2: SMC Settings
    smc_lookback_bars: int = 20
    smc_imbalance_ratio: float = 1.5      # Body must be 1.5x larger than prior total range
    smc_max_sweep_window: int = 3        # Imbalance must follow sweep within 3 bars

    # Strategy 3: Moving Averages
    ma_fast_sma: int = 5
    ma_slow_ema: int = 9
    ma_cross_window: int = 2             # Signal valid if cross occurred within 2 bars
    ma_risk_lookback: int = 10           # Lookback for local swing low calculation

    # ── Direction toggles ──
    allow_long: bool = True
    allow_short: bool = True

    # ── Risk & sizing ──
    risk_percent: float = Field(default=1.0, ge=0.05, le=5.0)
    max_position_pct: float = Field(default=15.0, ge=1.0, le=100.0)
    account_equity: float = Field(default=100_000.0, gt=0)

    # ── Tiered take-profit ──
    tiered_tp: TieredTPConfig = Field(default_factory=TieredTPConfig)

    # ── Scanner scope ──
    symbols: List[str] = Field(default_factory=list, description="Empty = scan all stored coins")

    # ── Warmup ──
    warmup_bars_4h: int = Field(default=50, ge=20, le=200, description="Min 4H bars before first signal")
    warmup_bars_15m: int = Field(default=60, ge=20, le=300, description="Min 15min bars before first signal")


ScalpingConfig = EngineConfig


def default_config() -> EngineConfig:
    return EngineConfig()