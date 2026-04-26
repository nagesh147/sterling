from pydantic import BaseModel, Field
from typing import List, Optional


class BacktestRequest(BaseModel):
    underlying: str
    lookback_days: int = Field(default=30, ge=7, le=365)
    sample_every_n_bars: int = Field(default=4, ge=1, le=24)


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
    st_values: List[float] = []   # [ST(7,3), ST(14,2), ST(21,1)] line levels
    state: str
    direction: str
    # Forward returns (% change) from this bar — None if insufficient future data
    fwd_return_4h: Optional[float] = None    # 4 bars ahead (4H)
    fwd_return_12h: Optional[float] = None   # 12 bars ahead (12H)
    fwd_return_24h: Optional[float] = None   # 24 bars ahead (1D)


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
    # Signal quality metrics (4H forward horizon)
    arrow_long_win_rate_4h: Optional[float] = None   # % green arrows where 4H return > 0
    arrow_short_win_rate_4h: Optional[float] = None  # % red arrows where 4H return < 0
    setup_long_avg_return_4h: Optional[float] = None # avg 4H return on confirmed long setups
    setup_short_avg_return_4h: Optional[float] = None
    signal_accuracy_long_4h: Optional[float] = None  # % all_green bars where 4H return > 0
    signal_accuracy_short_4h: Optional[float] = None
    # 12H horizon
    arrow_long_win_rate_12h: Optional[float] = None
    arrow_short_win_rate_12h: Optional[float] = None
    setup_long_avg_return_12h: Optional[float] = None
    setup_short_avg_return_12h: Optional[float] = None


class BacktestResult(BaseModel):
    underlying: str
    lookback_days: int
    sample_every_n_bars: int
    total_1h_candles: int
    total_4h_candles: int
    bars: List[BacktestBarResult]
    stats: BacktestStats
    timestamp_ms: int
