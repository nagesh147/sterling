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

    # ── Master System ──

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
    # Reconciled 2026-05-31 to the VALIDATED edge logic: the live scanner now
    # delegates to edge/strategies.py:signals_ma_crossover (EMA9 × EMA21 cross,
    # long-only, on the 4H series) — the exact function the edge feed trades and
    # the 270-config matrix validated (MA Crossover 4h BTC: Sharpe 1.83, +95%).
    # The old SMA(5)/EMA(9)-near-levels bidirectional logic was a different,
    # BTC-losing strategy (−40%). These SMA params are retained only for legacy
    # callers; the validated path uses EMA 9/21 fixed in the edge function.
    ma_fast_sma: int = 5
    ma_slow_ema: int = 9
    ma_cross_window: int = 2             # Signal valid if cross occurred within 2 bars
    ma_risk_lookback: int = 10           # Lookback for local swing low calculation
    # ATR bracket for the reconciled ma_crossover (validated "Intraday" profile:
    # SL 2.0×ATR, TP 3.5×ATR ⇒ R:R 1.75 on the 4H ATR).
    ma_atr_sl: float = Field(default=2.0, ge=0.5, le=6.0)
    ma_atr_tp: float = Field(default=3.5, ge=1.0, le=10.0)

    # Strategy 4: Mean Reversion
    mr_zscore_window: int = 20
    mr_zscore_threshold: float = 2.0     # Z-Score beyond this is considered overextended

    # Strategy 5: Breakout Momentum
    bo_rsi_long_threshold: float = 60.0
    bo_rsi_short_threshold: float = 40.0
    # Retest-entry breakout (rebuilt 2026-06-01). The old version chased the
    # extended breakout candle with a stop at the just-broken level → 44/44
    # stop-outs. This waits for the break, then for price to PULL BACK and retest
    # the broken level, and enters on the hold with a tight stop just beyond it.
    bo_retest_lookback: int = Field(default=12, ge=3, le=60,
                                    description="Bars to look back for the breakout thrust")
    bo_retest_band_pct: float = Field(default=0.4, ge=0.1, le=2.0,
                                      description="Retest zone width as % of the level price")

    # Strategy 6: Delta-Gamma Risk Surface
    dg_gex_flip_threshold: float = 0.0   # Positive vs Negative Gamma environment
    dg_wall_proximity_pct: float = 0.005 # 0.5% proximity to a major call/put wall
    dg_filter_breakouts: bool = True     # Reject breakouts in high positive gamma (low vol) environments

    # ── Direction toggles ──
    allow_long: bool = True
    allow_short: bool = True

    # ── Re-entry cooldown (auto-exec) ──
    # After a position for a symbol+strategy+direction closes, the algo waits
    # this many minutes before re-entering the SAME setup. 0 disables. Manual
    # clicks are exempt.
    # DEFAULT 0 (OFF): a 13.5-month bar-replay (4h/15m, BTC+ETH+SOL) showed ANY
    # cooldown removes net-positive trades — mean_reversion is +123 R and its
    # edge IS rapid re-entry; a 45m cooldown cut it to +13 R, and even 10m
    # craters the blended book from +33 R to -97 R. The May-30 ETH-short cluster
    # that motivated this was an unlucky local window of a strongly +EV strategy,
    # NOT a structural flaw. The mechanism is kept for manual opt-in if live
    # churn recurs, but it must not throttle the validated edge by default.
    reentry_cooldown_min: int = Field(default=0, ge=0, le=720)

    # ── Macro-trend filter ──
    # When on, counter-trend setups are suppressed: longs only in a 4H uptrend,
    # shorts only in a downtrend (chop allows both). Regime = 4H EMA(fast) vs
    # EMA(slow) with a flat dead-band.
    # Default ON: live paper auto-exec showed counter-trend setups (e.g. fading
    # bounces) bleeding when the higher-TF trend ran them over. Trend-aligned
    # setups carry a higher PF; the variance reduction is worth the trade-count.
    macro_trend_filter: bool = True
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
    symbols: List[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"], description="Empty = scan all stored coins")

    # ── Warmup ──
    warmup_bars_4h: int = Field(default=50, ge=20, le=200, description="Min 4H bars before first signal")
    warmup_bars_15m: int = Field(default=60, ge=20, le=300, description="Min 15min bars before first signal")


ScalpingConfig = EngineConfig


def default_config() -> EngineConfig:
    """Returns the default multi-track configuration using optimized Strategy+Timeframe pairs."""
    return EngineConfig(
        active_profiles=["swing_4h", "intraday_5m", "scalping_1m"],
        profiles={
            # 1. Swing - Highest Quality (1d/4h structure)
            "swing_4h": ScalpingProfile(
                macro_timeframe="1d",
                execution_timeframe="4h",
                pa_confirm_bars=3,
                risk_percent=1.0,
            ),
            # 2. Intraday - Top Overall Return (1h/5m structure)
            "intraday_5m": ScalpingProfile(
                macro_timeframe="1h",
                execution_timeframe="5m",
                pa_confirm_bars=3,
                risk_percent=0.5,
            ),
            # 3. Scalping - High Volatility (15m/1m structure)
            "scalping_1m": ScalpingProfile(
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