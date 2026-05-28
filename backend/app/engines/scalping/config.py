"""Configuration for the 4H+15min scalping strategies.

All three strategies (Price Action, SMC, MA Crossover) share the same risk
and timeframe config. Each can be independently enabled/disabled.
"""
from __future__ import annotations

from typing import Dict, List

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


class ScalpingProfile(BaseModel):
    """Configuration for a specific timeframe track/profile."""

    # Timeframe Controls — 4h structure / 30m execution is the default.
    # Over ~2y of real data (OOS) the top pairs cluster at PF ~1.4 (4h/5m 1.46,
    # 2h/15m 1.44, 4h/30m 1.42). 4h/30m is chosen as the default for the best RISK
    # profile, not the highest raw PF: highest win-rate (48.5%), lowest drawdown
    # (7.4R, ~half its PF-rivals), and fewest trades ⇒ least fee/slippage drag.
    # Higher-return alternatives (4h/5m, 2h/15m) carry ~2x the drawdown — pick them
    # in settings if chasing return. A saved config overrides this default.
    execution_timeframe: str = "30m"
    macro_timeframe: str = "4h"

    # ── Strategy toggles ──
    enable_price_action: bool = True
    enable_smc: bool = True
    enable_ma_crossover: bool = True
    enable_mean_reversion: bool = True
    enable_breakout: bool = True
    enable_delta_gamma: bool = True

    # ── 4H level detection ──
    level_touches: int = Field(default=2, ge=2, le=10, description="Min touches to qualify a level")
    level_tolerance_pct: float = Field(default=0.5, ge=0.1, le=3.0, description="% tolerance around level")

    # Strategy 1: Price Action Settings
    pa_lookback_bars: int = 30
    pa_confirm_bars: int = Field(
        default=3, ge=1, le=10,
        description="Breakout counts if it closed within the last N bars and price "
                    "is still beyond the neckline (1 = current bar only).",
    )
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

    # Strategy 4: Mean Reversion
    mr_zscore_window: int = 20
    mr_zscore_threshold: float = 2.0     # Z-Score beyond this is considered overextended

    # Strategy 5: Breakout Momentum
    bo_rsi_long_threshold: float = 60.0
    bo_rsi_short_threshold: float = 40.0

    # Strategy 6: Delta-Gamma Risk Surface
    dg_gex_flip_threshold: float = 0.0   # Positive vs Negative Gamma environment
    dg_wall_proximity_pct: float = 0.005 # 0.5% proximity to a major call/put wall
    dg_filter_breakouts: bool = True     # Reject breakouts in high positive gamma (low vol) environments

    # ── Direction toggles ──
    allow_long: bool = True
    allow_short: bool = True

    # ── Macro-trend filter (opt-in) ──
    # When on, counter-trend setups are suppressed: longs only in a 4H uptrend,
    # shorts only in a downtrend (chop allows both). Off by default — counter-
    # trend setups are still positive-EV, so forcing this trades total return for
    # a higher per-trade PF / lower variance. Regime = 4H EMA(fast) vs EMA(slow)
    # with a flat dead-band.
    macro_trend_filter: bool = False
    macro_trend_ema_fast: int = Field(default=50, ge=5, le=200)
    macro_trend_ema_slow: int = Field(default=100, ge=20, le=400)
    macro_trend_flat_band_pct: float = Field(
        default=0.5, ge=0.0, le=5.0,
        description="|emaFast−emaSlow|/price below this % ⇒ chop (both directions allowed)",
    )

    # ── Risk & sizing ──
    risk_percent: float = Field(default=1.0, ge=0.05, le=5.0)
    max_position_pct: float = Field(default=15.0, ge=1.0, le=100.0)
    account_equity: float = Field(default=100_000.0, gt=0)
    # Minimum reward:risk a setup must clear to arm (target ≥ min_rr × stop).
    # Default 1.5 matches the previously-hardcoded gate — no behavior change.
    min_rr: float = Field(default=1.5, ge=0.5, le=5.0)
    # Maximum stop distance allowed as a multiple of ATR. Rejects unscalpable setups.
    max_stop_atr: float = Field(default=4.0, ge=1.0, le=10.0)


class EngineConfig(BaseModel):
    """The root configuration for the scalping module, managing multiple profiles."""
    active_profiles: List[str] = Field(default_factory=lambda: ["intraday"])
    profiles: Dict[str, ScalpingProfile] = Field(default_factory=dict)
    
    # Global settings
    use_optimized: bool = False

    # ── Tiered take-profit ──
    tiered_tp: TieredTPConfig = Field(default_factory=TieredTPConfig)

    # ── Scanner scope ──
    symbols: List[str] = Field(default_factory=list, description="Empty = scan all stored coins")

    # ── Warmup ──
    warmup_bars_4h: int = Field(default=50, ge=20, le=200, description="Min 4H bars before first signal")
    warmup_bars_15m: int = Field(default=60, ge=20, le=300, description="Min 15min bars before first signal")


ScalpingConfig = EngineConfig


def default_config() -> EngineConfig:
    """Returns the default multi-track configuration."""
    return EngineConfig(
        active_profiles=["intraday"],
        profiles={
            "intraday": ScalpingProfile(
                macro_timeframe="4h",
                execution_timeframe="15m",
                pa_confirm_bars=3,
                risk_percent=1.0,
            ),
            "scalping": ScalpingProfile(
                macro_timeframe="1h",
                execution_timeframe="5m",
                pa_confirm_bars=3,
                risk_percent=0.5,
            ),
            "aggressive": ScalpingProfile(
                macro_timeframe="15m",
                execution_timeframe="1m",
                pa_confirm_bars=1,
                risk_percent=0.25,
            ),
        }
    )


# ── Timeframe presets ────────────────────────────────────────────────────────
# One-click bundles mapping to the three pairs the 2-year OOS study highlighted.
# Applying a preset only sets macro/execution TF + confirm bars on the active
# config — it never touches risk, symbols, or other settings. confirm_bars is 3
# (the value every reported metric was measured at). Trailing is intentionally NOT
# a preset field: scalping trails on a %-based stop (separately validated), and the
# TF study used fixed SL/TP, so per-preset ATR trail multiples would be unvalidated.

class TimeframePreset(BaseModel):
    label: str                 # short display name (Intraday / Scalping / Aggressive)
    macro_tf: str
    exec_tf: str
    confirm_bars: int
    suggested_risk_pct: float  # recommended per-trade risk for this profile (guidance)
    oos_win_pct: float         # 2-year out-of-sample reference metrics (Price Action)
    oos_pf: float
    oos_max_dd_r: float
    description: str           # when to use


# Reference metrics are the 2-year OOS study (Price Action, defaults) — a measured,
# overfit-prone edge, NOT a guarantee. Ordered intraday → scalping → aggressive.
TIMEFRAME_PRESETS: Dict[str, TimeframePreset] = {
    "CONSERVATIVE_DEFAULT": TimeframePreset(
        label="Intraday", macro_tf="4h", exec_tf="30m", confirm_bars=3, suggested_risk_pct=1.0,
        oos_win_pct=48.5, oos_pf=1.42, oos_max_dd_r=7.4,
        description="Default. Fewest, cleanest trades; lowest drawdown & best win-rate; least fee drag. Hold hours.",
    ),
    "STRUCTURAL_SCALP": TimeframePreset(
        label="Scalping", macro_tf="2h", exec_tf="15m", confirm_bars=3, suggested_risk_pct=0.5,
        oos_win_pct=44.4, oos_pf=1.44, oos_max_dd_r=16.6,
        description="More frequent entries; balanced edge but ~2x the drawdown — size smaller.",
    ),
    "AGGRESSIVE_RETURN": TimeframePreset(
        label="Aggressive", macro_tf="4h", exec_tf="5m", confirm_bars=3, suggested_risk_pct=0.5,
        oos_win_pct=42.0, oos_pf=1.46, oos_max_dd_r=13.0,
        description="Highest return & most trades, but heavy 5m fees/slippage not modeled — needs tight execution.",
    ),
}