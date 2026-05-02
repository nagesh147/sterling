from pydantic import BaseModel, Field
from typing import List, Optional


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
