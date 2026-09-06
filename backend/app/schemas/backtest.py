"""Indian-market unified backtest schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field



class UnifiedBacktestRequest(BaseModel):
    strategy: str = Field(
        default="adaptive_edge",
        description="Strategy to backtest: adaptive_edge, supertrend, navigator, directional, mean_reversion",
    )
    symbol: str = Field(default="NIFTY 50", description="Primary tradingsymbol or universe label")
    instrument_scope: str = Field(
        default="single",
        description="Scope of instruments: 'single', 'indices', 'fno_all', 'fno_selected'",
    )
    scan_indices: List[str] = Field(
        default_factory=lambda: ["NIFTY 50", "NIFTY BANK"],
        description="List of index symbols when scanning indices",
    )
    scan_stocks: List[str] = Field(
        default_factory=lambda: ["RELIANCE", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "TCS"],
        description="List of selected F&O stock symbols",
    )
    scan_all_stocks: bool = Field(default=False, description="Scan full eligible ~180+ F&O universe")
    contract_type: str = Field(
        default="futures",
        description="Contract type to simulate: 'futures', 'options_atm', 'options_itm', 'options_otm', 'spot'",
    )
    expiry_cycle: str = Field(
        default="weekly",
        description="Expiry cycle to trade: 'weekly' or 'monthly'",
    )
    strike_moneyness: List[str] = Field(
        default_factory=lambda: ["ATM"],
        description="Strike moneyness resolved: ['ATM'], ['ITM', 'ATM'], etc.",
    )
    data_source: str = Field(
        default="kite",
        description="Historical data source provider: 'kite' (Zerodha Kite) or 'truedata' (TrueData V2.6)",
    )
    dynamic_mode: bool = Field(
        default=True,
        description="Dynamic Autonomous Mode: calculates dynamic ATR Stop Loss, Volatility TP, and Break-Even/TSL upgrades automatically per trade",
    )
    timeframe: str = Field(default="5m", description="Candle timeframe: 1m, 3m, 5m, 15m, 30m, 1h, mtf_confluence")
    lookback_days: int = Field(default=30, ge=3, le=365, description="Lookback window in calendar days")
    starting_capital: float = Field(default=100000.0, ge=1000.0, description="Starting capital in INR")
    lot_size: Optional[int] = Field(default=None, description="Lot size override (e.g. 25 for Nifty, 15 for BankNifty)")
    num_lots: int = Field(default=1, ge=1, le=100, description="Number of lots traded per setup")
    slippage_points: float = Field(default=0.5, ge=0.0, le=20.0, description="Slippage buffer in points per fill")
    brokerage_per_order: float = Field(default=20.0, ge=0.0, description="Flat brokerage in INR per order")
    stt_pct: float = Field(default=0.0002, ge=0.0, description="STT rate on sell turnover (0.02% for Futures, 0.1% for Options)")
    stop_points: Optional[float] = Field(default=None, description="Manual hard stop override in points (if dynamic_mode is disabled)")
    target_points: Optional[float] = Field(default=None, description="Manual profit target override in points (if dynamic_mode is disabled)")
    trail_points: Optional[float] = Field(default=None, description="Manual trailing stop override in points (if dynamic_mode is disabled)")
    session_cutoff_hour: int = Field(default=15, ge=9, le=15, description="Intraday session cutoff hour (IST)")
    session_cutoff_min: int = Field(default=15, ge=0, le=59, description="Intraday session cutoff minute (IST)")
    strategy_params: Dict[str, Any] = Field(default_factory=dict, description="Custom hyperparameters for selected strategy")


class BacktestTradeLog(BaseModel):
    trade_id: int
    entry_time: str
    exit_time: str
    symbol: Optional[str] = None
    direction: str   # LONG or SHORT
    entry_price: float
    exit_price: float
    qty: int
    sl_points: Optional[float] = None
    tp_points: Optional[float] = None
    reward_to_risk: Optional[float] = None
    gross_pnl: float
    friction_cost: float
    net_pnl: float
    return_pct: float
    mae_points: float
    mfe_points: float
    holding_bars: int
    exit_reason: str  # TARGET, STOP_LOSS, TRAILING_STOP, SESSION_CUTOFF, SIGNAL_REVERSAL


class PerformanceMetrics(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    profit_factor: float
    net_pnl_inr: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_inr: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    payoff_ratio: float
    avg_win_inr: float
    avg_loss_inr: float
    expectancy_inr: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    total_friction_inr: float
    friction_drag_pct: float


class EquityPoint(BaseModel):
    timestamp: str
    equity: float
    drawdown_pct: float
    high_water_mark: float


class MonteCarloResult(BaseModel):
    simulations: int
    mean_return_pct: float
    median_return_pct: float
    p5_return_pct: float
    p95_return_pct: float
    p95_max_drawdown_pct: float
    prob_profit_pct: float


class UnifiedBacktestResult(BaseModel):
    strategy: str
    symbol: str
    timeframe: str
    data_source: str
    candles_evaluated: int
    start_date: str
    end_date: str
    starting_capital: float
    ending_capital: float
    metrics: PerformanceMetrics
    equity_curve: List[EquityPoint]
    trades: List[BacktestTradeLog]
    monte_carlo: Optional[MonteCarloResult] = None
    timestamp_ms: int


