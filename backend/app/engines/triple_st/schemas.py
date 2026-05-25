"""Pydantic request/response shapes for the Triple SuperTrend API.

These wrap the engine's internal dataclasses for JSON transport. `TripleSTConfig`
itself lives in `config.py` and is reused here as both a request body and an
echoed field so the UI always renders against the exact parameters used.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from app.engines.triple_st.config import (
    TripleSTConfig,
    StrategyMode,
    AssetClass,
)


# ─── Shared view models ──────────────────────────────────────────────────────


class STLineView(BaseModel):
    period: int
    multiplier: float
    value: float
    trend: int                 # +1 bull / -1 bear


class QualityView(BaseModel):
    consensus: float
    volume: float
    htf: float
    regime: float
    momentum: float
    bonus: float
    total: float
    threshold: float
    passed: bool


class FilterView(BaseModel):
    name: str
    passed: bool
    detail: str


class RegimeView(BaseModel):
    is_compressed: bool
    is_high_vol: bool
    is_trending: bool
    is_choppy: bool
    post_squeeze: bool
    adx: float
    chop: float
    bb_ratio: float
    label: str


class TradePlanView(BaseModel):
    direction: str
    entry: float
    stop_loss: float
    take_profit: float
    r_distance: float
    partials: List[Tuple[float, float]]
    size_units: float
    notional_usd: float
    risk_usd: float
    risk_pct: float
    leverage: float
    rr: float


# ─── Live evaluation ─────────────────────────────────────────────────────────


class StrategyEvaluation(BaseModel):
    underlying: str
    timestamp_ms: int
    close: float
    effective_mode: StrategyMode
    asset_class: AssetClass

    # signal
    direction: str             # "long" | "short" | "none"
    raw_long: bool
    raw_short: bool
    arrow: bool
    consensus_count: int
    supertrends: List[STLineView]

    quality: QualityView
    filters: List[FilterView]
    regime: RegimeView

    entry_ok: bool             # strict auto-arm (min_confirm + quality + filters + can_trade)
    executable: bool           # a directional plan exists AND not capital-halted (manual exec ok)
    can_trade: bool
    block_reason: str          # capital-protection reason when can_trade is False
    reason: str

    trade_plan: Optional[TradePlanView] = None

    # capital-protection snapshot
    equity: float
    drawdown_pct: float
    consecutive_losses: int
    size_multiplier: float
    effective_quality_threshold: float

    config: TripleSTConfig
    warming_up: bool = False


# ─── Multi-symbol scan (signals-first view) ──────────────────────────────────


class SignalSummary(BaseModel):
    """Compact per-symbol signal row for the scanner list."""
    underlying: str
    close: float
    direction: str             # "long" | "short" | "none"
    entry_ok: bool
    arrow: bool
    consensus_count: int
    quality_total: float
    quality_pass: bool
    regime_label: str
    effective_mode: StrategyMode
    asset_class: AssetClass
    executable: bool = False   # plan exists AND not capital-halted → EXECUTE allowed
    # trade plan (present when a direction is active)
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rr: Optional[float] = None
    risk_pct: Optional[float] = None
    leverage: Optional[float] = None
    notional_usd: Optional[float] = None
    size_units: Optional[float] = None
    reason: str = ""
    timestamp_ms: int = 0
    error: Optional[str] = None


class SignalScanResponse(BaseModel):
    signals: List[SignalSummary]
    count: int
    armed_count: int
    effective_mode: StrategyMode
    timestamp_ms: int


# ─── Backtest ────────────────────────────────────────────────────────────────


class BacktestRequest(BaseModel):
    underlying: str
    # Up to 3 years; actual span is bounded by locally-stored history (~2y).
    lookback_days: int = Field(default=365, ge=14, le=1095)
    config: Optional[TripleSTConfig] = None    # overrides server config when set


class BacktestTrade(BaseModel):
    direction: str
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float          # size-weighted average exit
    bars_held: int
    pnl_usd: float
    pnl_r: float               # P&L in R-multiples
    exit_reasons: List[str]
    mode: str


class EquityPoint(BaseModel):
    ts: int
    equity: float


class BacktestStats(BaseModel):
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe: float
    total_return_pct: float
    long_trades: int
    short_trades: int
    avg_bars_held: float
    final_equity: float


class TripleSTBacktestResult(BaseModel):
    underlying: str
    lookback_days: int
    bars_evaluated: int
    config: TripleSTConfig
    asset_class: AssetClass
    stats: BacktestStats
    trades: List[BacktestTrade]
    equity_curve: List[EquityPoint]
    timestamp_ms: int


# ─── Config endpoint ─────────────────────────────────────────────────────────


class ModePresetView(BaseModel):
    mode: StrategyMode
    min_confirm: int
    risk_mult: float
    be_trigger_r: float
    trail_source: str
    partials: List[Tuple[float, float]]


class AssetPresetView(BaseModel):
    asset_class: AssetClass
    sl_mult: float
    tp_mult: float
    min_adx: float
    squeeze_threshold: float
    short_modifier: float


class ConfigResponse(BaseModel):
    config: TripleSTConfig
    mode_presets: List[ModePresetView]
    asset_presets: List[AssetPresetView]


# ─── Execution ───────────────────────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    underlying: str
    # When omitted the server recomputes the live trade plan before routing.
    confirm: bool = True


class ExecuteResponse(BaseModel):
    accepted: bool
    mode: str                  # "paper" | "live"
    underlying: str
    direction: str
    size_units: float
    notional_usd: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    order_id: Optional[str] = None
    paper_position_id: Optional[str] = None
    status: str
    reason: str
    timestamp_ms: int
