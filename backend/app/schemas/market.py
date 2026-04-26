from pydantic import BaseModel
from typing import List, Optional


class Candle(BaseModel):
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketSnapshotResponse(BaseModel):
    underlying: str
    spot_price: float
    index_price: float
    perp_price: float
    candles_4h_count: int
    candles_1h_count: int
    candles_15m_count: int
    dvol: Optional[float] = None
    ivr: Optional[float] = None
    data_source: str
    timestamp_ms: int


class OptionSummary(BaseModel):
    instrument_name: str
    underlying: str
    strike: float
    expiry_date: str
    dte: int
    option_type: str  # "call" | "put"
    bid: float
    ask: float
    mark_price: float
    mid_price: float
    mark_iv: float
    delta: float
    open_interest: float
    volume_24h: float
    last_updated_ms: int
