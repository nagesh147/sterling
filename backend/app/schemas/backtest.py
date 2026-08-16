from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class BacktestRequest(BaseModel):
    underlying: str
    lookback_days: int = Field(default=30, ge=7, le=365)
    sample_every_n_bars: int = Field(default=4, ge=1, le=24)
    # Optional Black-Scholes pricing — pass current ATM IV (e.g. 0.80 = 80%)
    # to get theoretical option P&L alongside candle returns.
    atm_iv: Optional[float] = Field(default=None, ge=0.01, le=5.0)
    option_dte: int = Field(default=30, ge=7, le=90)


class BacktestBarResult(BaseModel):
    timestamp_ms: int
    close_1h: float
    close_4h: float
    macro_regime: str
    ema50: float
    signal_trend: int
    all_green: bool
    all_red: bool
    green_arrow: bool
    red_arrow: bool
    st_trends: List[int]
    st_values: List[float] = []
    state: str
    direction: str
    signal_score: Optional[float] = None   # 0-20 confluence score from signal engine
    # Spot forward returns (% change)
    fwd_return_4h: Optional[float] = None
    fwd_return_12h: Optional[float] = None
    fwd_return_24h: Optional[float] = None
    # Black-Scholes option P&L (% of entry premium) — only when atm_iv supplied
    bs_entry_premium: Optional[float] = None   # theoretical entry cost per lot
    bs_fwd_pnl_4h: Optional[float] = None      # option P&L % at 4H exit
    bs_fwd_pnl_12h: Optional[float] = None
    bs_fwd_pnl_24h: Optional[float] = None


class BacktestStats(BaseModel):
    total_bars_evaluated: int
    bullish_regime_bars: int
    bearish_regime_bars: int
    neutral_regime_bars: int
    bullish_signal_bars: int
    bearish_signal_bars: int
    neutral_signal_bars: int
    green_arrows: int
    red_arrows: int
    confirmed_long_setups: int
    confirmed_short_setups: int
    early_long_setups: int
    early_short_setups: int
    filtered_bars: int
    idle_bars: int
    # Signal quality — 4H horizon
    arrow_long_win_rate_4h: Optional[float] = None
    arrow_short_win_rate_4h: Optional[float] = None
    setup_long_avg_return_4h: Optional[float] = None
    setup_short_avg_return_4h: Optional[float] = None
    signal_accuracy_long_4h: Optional[float] = None
    signal_accuracy_short_4h: Optional[float] = None
    # 12H horizon
    arrow_long_win_rate_12h: Optional[float] = None
    arrow_short_win_rate_12h: Optional[float] = None
    setup_long_avg_return_12h: Optional[float] = None
    setup_short_avg_return_12h: Optional[float] = None
    # BS option P&L stats — present only when atm_iv was supplied
    bs_arrow_long_avg_pnl_4h: Optional[float] = None   # avg option P&L % on green arrows
    bs_arrow_short_avg_pnl_4h: Optional[float] = None
    bs_arrow_long_win_rate_4h: Optional[float] = None  # % profitable at 4H
    bs_arrow_short_win_rate_4h: Optional[float] = None


class BacktestResult(BaseModel):
    underlying: str
    lookback_days: int
    sample_every_n_bars: int
    total_1h_candles: int
    total_4h_candles: int
    bars: List[BacktestBarResult]
    stats: BacktestStats
    timestamp_ms: int
    # Echoed back so UI can label the results
    atm_iv_used: Optional[float] = None
    option_dte_used: Optional[int] = None
    # Position-level simulation (fees applied, non-overlapping trades)
    sim_equity_curve:   Optional[List[float]] = None
    sim_trade_count:    Optional[int]         = None
    sim_win_rate:       Optional[float]       = None
    sim_expectancy_pct: Optional[float]       = None
    sim_profit_factor:  Optional[float]       = None
    sim_max_drawdown:   Optional[float]       = None
    sim_sharpe:         Optional[float]       = None
    sim_fee_rt_pct:     Optional[float]       = None


# ── Multi-Timeframe Backtest ──────────────────────────────────────────────────

class MTFProfileResult(BaseModel):
    underlying:          str
    label:               str
    signal_tf:           str
    regime_tf:           str
    total_signal_bars:   int
    total_regime_bars:   int
    total_trades:        int
    win_rate:            Optional[float] = None
    sharpe:              Optional[float] = None
    calmar:              Optional[float] = None
    sortino:             Optional[float] = None
    profit_factor:       Optional[float] = None
    max_drawdown:        Optional[float] = None
    avg_rr:              Optional[float] = None
    fwd1_label:          str = ""
    fwd1_long_win_rate:  Optional[float] = None
    fwd1_short_win_rate: Optional[float] = None
    fwd2_label:          str = ""
    fwd2_long_win_rate:  Optional[float] = None
    fwd2_short_win_rate: Optional[float] = None
    fwd3_label:          str = ""
    fwd3_long_win_rate:  Optional[float] = None
    fwd3_short_win_rate: Optional[float] = None
    equity_curve:        List[float] = []
    regime_breakdown:    dict = {}


class MTFBacktestRequest(BaseModel):
    underlying:    str
    lookback_days: int = Field(default=30, ge=7, le=90)
    profiles:      List[str] = Field(
        default=["scalping_15m", "intraday_1h"],
        description="Profile keys to run. Options: scalping_15m, intraday_1h, intraday_4h",
    )
    score_min: float = Field(default=0.0, ge=0.0, le=20.0)
    # Issue 11 — per-8h funding rate override. None → endpoint applies the
    # conservative default from app/services/funding.py for the underlying.
    funding_8h_pct: Optional[float] = Field(
        default=None,
        description="Override perpetual funding rate per 8h period (e.g. 0.0001 = 1 bp). None uses a per-underlying default.",
    )
    # Issue 6 — exit ATR timeframe override.
    exit_atr_tf: Optional[str] = Field(
        default=None,
        description='"signal" or "regime". None uses each profile\'s default.',
    )
    # Issue 7 — payoff mode override.
    payoff_mode: Optional[str] = Field(
        default=None,
        description='"fixed_2r" (legacy) or "chandelier_trail". None uses each profile\'s default.',
    )


class MTFBacktestResult(BaseModel):
    underlying:   str
    profiles:     Dict[str, Any]
    timestamp_ms: int
    recommended:  Optional[str] = None


# ── Hybrid VCP-Momentum Scalper ───────────────────────────────────────────────

class HybridVCPProfileResult(BaseModel):
    label:        str
    signal_tf:    str
    regime_tf:    str
    trade_count:  int
    win_rate:     Optional[float] = None
    sharpe:       Optional[float] = None
    sortino:      Optional[float] = None
    profit_factor: Optional[float] = None
    max_drawdown: Optional[float] = None
    cagr:         Optional[float] = None
    equity_curve: List[float] = []
    trades:       List[Dict[str, Any]] = []


class HybridVCPBacktestRequest(BaseModel):
    underlying:    str
    lookback_days: int = Field(default=30, ge=7, le=90)
    profiles: List[str] = Field(
        default=["btc_scalping_15m", "btc_scalping_30m", "eth_scalping_15m", "eth_scalping_30m"],
        description="Which VCP profiles to run. Options: btc_scalping_15m, btc_scalping_30m, eth_scalping_15m, eth_scalping_30m",
    )
    funding_8h_pct: Optional[float] = Field(
        default=None,
        description="Override perpetual funding rate per 8h period.",
    )
    apply_slippage: bool = Field(default=True, description="Apply tiered slippage to exits.")


class HybridVCPBacktestResult(BaseModel):
    underlying:   str
    profiles:     Dict[str, HybridVCPProfileResult]
    timestamp_ms: int
    recommended:  Optional[str] = None


# ── Unified Institutional Multi-Strategy Backtest (Real Data Only) ────────────

class UnifiedBacktestRequest(BaseModel):
    strategy: str = Field(
        default="adaptive_edge",
        description="Strategy to backtest: adaptive_edge, supertrend, navigator, directional, mean_reversion",
    )
    symbol: str = Field(default="NIFTY 50", description="Index, F&O equity tradingsymbol, or ALL_INDICES")
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
    stt_pct: float = Field(default=0.00125, ge=0.0, description="STT rate on sell side")
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

