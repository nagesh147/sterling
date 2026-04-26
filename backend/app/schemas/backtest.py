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
    state: str
    direction: str


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


class BacktestResult(BaseModel):
    underlying: str
    lookback_days: int
    sample_every_n_bars: int
    total_1h_candles: int
    total_4h_candles: int
    bars: List[BacktestBarResult]
    stats: BacktestStats
    timestamp_ms: int
