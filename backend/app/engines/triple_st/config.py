"""Configuration surface for the Triple SuperTrend strategy.

Everything tunable lives here:
  * `StrategyMode` / `AssetClass` enums
  * `MODE_TABLE`  — per-mode behaviour (confirmation count, risk multiplier,
    breakeven trigger, partial-profit ladder, trailing source, time-stop, and
    the drawdown-scaling thresholds used by capital protection)
  * `ASSET_TABLE` — per-asset-class tables (SL/TP ATR multipliers, volume-MA
    period, RSI buffer, min ADX, gap threshold, squeeze threshold, cooldown
    multiplier, short-side modifier)
  * `TripleSTConfig` — the operator-facing toggle/parameter bundle (mirrors the
    PineScript "USER INPUTS"), every filter independently switchable.

The numbers are adapted to this app's spot/perp candle data rather than copied
verbatim from PineScript; they are intentionally conservative and centralised
so a single edit re-tunes the whole pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class StrategyMode(str, Enum):
    AGGRESSIVE = "Aggressive"
    BALANCED = "Balanced"
    CONSERVATIVE = "Conservative"
    MOMENTUM = "Momentum"


class AssetClass(str, Enum):
    AUTO = "Auto-Detect"
    LARGE = "Large"
    MID = "Mid"
    SMALL = "Small"


class HTFSource(str, Enum):
    SUPERTREND = "SuperTrend"
    EMA = "EMA"
    BOTH = "Both"


# ─────────────────────────────────────────────────────────────────────────────
# Per-mode behaviour table
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ModeParams:
    """Behaviour knobs that change with the active trading mode."""
    min_confirm: int                 # SuperTrends that must agree to arm (2 or 3)
    risk_mult: float                 # multiplies the base risk% per trade
    be_trigger_r: float              # R-multiple at which stop moves to breakeven
    # partial-profit ladder: list of (R-multiple trigger, fraction-of-position)
    partials: Tuple[Tuple[float, float], ...]
    trail_source: str                # which SuperTrend trails the runner: "ST3"|"ST1"|"ST2"
    momentum_trail: bool             # use ST1/ST2 fail-counter trailing (Momentum)
    time_stop_pre_be: int            # strict bar budget before breakeven is reached
    time_stop_post_be: float         # lenient multiplier on the budget after BE
    # Drawdown-scaling thresholds (portfolio DD% → size multiplier). Sorted asc.
    dd_scaling: Tuple[Tuple[float, float], ...]


# min_confirm: Aggressive/Momentum need 2/3 SuperTrends; Balanced/Conservative need 3/3.
MODE_TABLE: Dict[StrategyMode, ModeParams] = {
    StrategyMode.AGGRESSIVE: ModeParams(
        min_confirm=2,
        risk_mult=1.25,
        be_trigger_r=0.4,
        partials=((1.5, 0.50),),
        trail_source="ST3",
        momentum_trail=False,
        time_stop_pre_be=6,
        time_stop_post_be=2.5,
        dd_scaling=((0.05, 0.75), (0.10, 0.50), (0.15, 0.25)),
    ),
    StrategyMode.BALANCED: ModeParams(
        min_confirm=3,
        risk_mult=1.0,
        be_trigger_r=0.5,
        partials=((1.0, 0.34), (2.0, 0.33)),
        trail_source="ST3",
        momentum_trail=False,
        time_stop_pre_be=10,
        time_stop_post_be=2.5,
        dd_scaling=((0.06, 0.75), (0.12, 0.50), (0.18, 0.25)),
    ),
    StrategyMode.CONSERVATIVE: ModeParams(
        min_confirm=3,
        risk_mult=0.70,
        be_trigger_r=0.5,
        partials=((1.0, 0.50),),
        trail_source="ST3",
        momentum_trail=False,
        time_stop_pre_be=14,
        time_stop_post_be=2.0,
        dd_scaling=((0.04, 0.75), (0.08, 0.50), (0.12, 0.25)),
    ),
    StrategyMode.MOMENTUM: ModeParams(
        min_confirm=2,
        risk_mult=1.10,
        be_trigger_r=0.5,
        partials=((2.0, 0.25),),
        trail_source="ST1",
        momentum_trail=True,
        time_stop_pre_be=8,
        time_stop_post_be=3.0,
        dd_scaling=((0.06, 0.75), (0.12, 0.50), (0.18, 0.25)),
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Per-asset-class table
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AssetParams:
    sl_mult: float            # ATR multiple for the initial stop
    tp_mult: float            # ATR multiple for the take-profit (also defines R for partials)
    vol_ma_period: int        # volume moving-average lookback
    rsi_buffer: float         # RSI midline buffer (long needs >50+buf, short <50-buf)
    min_adx: float            # minimum ADX for the regime to count as trending
    gap_threshold_pct: float  # bar-to-bar gap (%) that triggers gap protection
    squeeze_threshold: float  # BB-width percentile below which we call a squeeze
    cooldown_mult: float      # multiplies the base cooldown bars after an exit
    short_modifier: float     # extra size haircut applied to short-side trades


# Squeeze thresholds match the spec (Large 0.75 / Mid 0.80 / Small 0.85); the
# rest are tuned so smaller-cap (higher-ATR) assets get wider stops, stricter
# trend gating, and smaller short exposure.
ASSET_TABLE: Dict[AssetClass, AssetParams] = {
    AssetClass.LARGE: AssetParams(
        sl_mult=1.5, tp_mult=3.0, vol_ma_period=20, rsi_buffer=5.0,
        min_adx=20.0, gap_threshold_pct=1.5, squeeze_threshold=0.75,
        cooldown_mult=1.0, short_modifier=0.90,
    ),
    AssetClass.MID: AssetParams(
        sl_mult=1.8, tp_mult=3.2, vol_ma_period=24, rsi_buffer=7.0,
        min_adx=22.0, gap_threshold_pct=2.5, squeeze_threshold=0.80,
        cooldown_mult=1.2, short_modifier=0.80,
    ),
    AssetClass.SMALL: AssetParams(
        sl_mult=2.2, tp_mult=3.5, vol_ma_period=30, rsi_buffer=10.0,
        min_adx=25.0, gap_threshold_pct=4.0, squeeze_threshold=0.85,
        cooldown_mult=1.5, short_modifier=0.70,
    ),
}


def classify_asset(atr_percent: float) -> AssetClass:
    """Auto-detect asset class from ATR-as-%-of-price (volatility proxy).

    Large caps (BTC/ETH) sit ~1-2% ATR on 1H; mid ~2-4%; small >4%.
    """
    if atr_percent < 2.0:
        return AssetClass.LARGE
    if atr_percent < 4.0:
        return AssetClass.MID
    return AssetClass.SMALL


# ─────────────────────────────────────────────────────────────────────────────
# Operator-facing config (mirrors the PineScript USER INPUTS)
# ─────────────────────────────────────────────────────────────────────────────


# Triple SuperTrend definitions: (atr_period, atr_multiplier).
ST_CONFIGS: List[Tuple[int, float]] = [(7, 3.0), (14, 2.0), (21, 1.0)]


class TripleSTConfig(BaseModel):
    """All toggles + parameters. Every filter is independently switchable.

    Defaults match the PineScript spec. This object is the request body for
    `/config` and is echoed inside every evaluation/backtest response so the UI
    always renders against the exact parameters used.
    """

    mode: StrategyMode = StrategyMode.BALANCED

    # Lean Quality Score
    use_quality_score: bool = True
    quality_threshold: int = Field(default=68, ge=40, le=95)

    # Asset classification
    asset_type: AssetClass = AssetClass.AUTO

    # ── Filters (all toggleable) ──
    use_ha: bool = True               # Heiken-Ashi body confirmation
    use_volume: bool = True           # volume-ratio confirmation
    use_rsi: bool = True              # RSI midline + buffer
    use_macd: bool = True             # MACD histogram direction
    use_htf: bool = True              # higher-timeframe bias
    htf_source: HTFSource = HTFSource.BOTH
    use_btc_corr: bool = True         # BTC correlation alignment
    use_regime_filter: bool = True    # block entries in choppy/compressed regimes
    use_spike_guard: bool = True      # volatility-spike emergency guard
    use_gap_protection: bool = True   # gap emergency exit

    # ── Risk & management ──
    risk_percent: float = Field(default=0.75, ge=0.05, le=5.0)
    max_position_pct: float = Field(default=20.0, ge=1.0, le=100.0)
    daily_loss_limit: float = Field(default=4.0, ge=0.5, le=20.0)
    max_slippage: float = Field(default=0.6, ge=0.0, le=5.0)
    warmup_bars: int = Field(default=100, ge=30, le=500)

    # ── Capital protection / adaptation ──
    use_circuit_breaker: bool = True       # halt after N consecutive losses
    consecutive_loss_limit: int = Field(default=4, ge=2, le=10)
    use_black_swan: bool = True            # halt on >12% BTC daily move
    black_swan_pct: float = Field(default=12.0, ge=5.0, le=30.0)
    use_dynamic_mode: bool = True          # rolling-window auto mode switching

    # Account / sizing context (USD). Used for position-value caps and risk math.
    account_equity: float = Field(default=100_000.0, gt=0)


def default_config() -> TripleSTConfig:
    return TripleSTConfig()
