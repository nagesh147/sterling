from pydantic import BaseModel
from typing import List


class RegimeTrendBar(BaseModel):
    timestamp_ms: int
    close: float
    ema50: float
    is_bullish: bool
    regime: str  # "bullish" | "bearish" | "neutral"


class RegimeTrendResponse(BaseModel):
    underlying: str
    bars: List[RegimeTrendBar]
    count: int
