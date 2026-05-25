"""Pydantic request/response shapes for the daily SMA/EMA + RSI/ADX strategy.

These wrap the engine's internal dataclasses for JSON transport. `TripleSTConfig`
itself lives in `config.py` and is reused here as both a request body and an
echoed field so the UI always renders against the exact parameters used.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.engines.triple_st.config import TripleSTConfig


# ─── Shared view models ──────────────────────────────────────────────────────


class TradePlanView(BaseModel):
    direction: str
    entry: float
    stop_loss: float
    r_distance: float
    size_units: float
    notional_usd: float
    risk_usd: float
    risk_pct: float
    leverage: float


# ─── Live evaluation ─────────────────────────────────────────────────────────


class StrategyEvaluation(BaseModel):
    underlying: str
    timestamp_ms: int
    close: float
    timeframe: str

    # signal
    direction: str             # "long" | "short" | "none"

    # indicator values (at the last closed daily bar)
    sma: float                 # trend SMA (regime filter)
    rsi: float                 # RSI(rsi_period)
    rsi_oversold: float        # long entry threshold (RSI <)
    rsi_exit: float            # long exit threshold (RSI >)

    # conditions
    in_uptrend: bool           # close > SMA(trend)
    oversold: bool             # RSI < rsi_oversold (long trigger)

    entry_ok: bool             # a direction is armed
    executable: bool           # a plan exists AND trading is not halted
    can_trade: bool
    block_reason: str
    reason: str

    trade_plan: Optional[TradePlanView] = None

    equity: float
    config: TripleSTConfig
    warming_up: bool = False


# ─── Multi-symbol scan (signals-first view) ──────────────────────────────────


class SignalSummary(BaseModel):
    """Compact per-symbol signal row for the scanner list."""
    underlying: str
    close: float
    direction: str             # "long" | "short" | "none"
    entry_ok: bool
    executable: bool = False

    # indicators + conditions
    sma: float = 0.0           # trend SMA
    rsi: float = 0.0
    rsi_oversold: float = 10.0
    rsi_exit: float = 70.0
    in_uptrend: bool = False
    oversold: bool = False

    # trade plan (present when a direction is active)
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    r_distance: Optional[float] = None
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
    exit_price: float
    bars_held: int
    pnl_usd: float
    pnl_r: float               # P&L in R-multiples
    exit_reason: str


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
    stats: BacktestStats
    trades: List[BacktestTrade]
    equity_curve: List[EquityPoint]
    timestamp_ms: int


# ─── Config endpoint ─────────────────────────────────────────────────────────


class ConfigResponse(BaseModel):
    config: TripleSTConfig


class UniverseResponse(BaseModel):
    symbols: List[str]          # all selectable underlyings (have enough history)


# ─── Recent signal history ───────────────────────────────────────────────────


class HistoryTrade(BaseModel):
    underlying: str
    direction: str
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    bars_held: int
    pnl_r: float
    exit_reason: str


class HistoryResponse(BaseModel):
    trades: List[HistoryTrade]  # most recent first
    count: int
    wins: int
    win_rate: float
    timestamp_ms: int


# ─── Execution ───────────────────────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    underlying: str
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
