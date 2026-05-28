"""Schemas for the Statistical Arbitrage (3D Spread) Engine."""
from pydantic import BaseModel
from typing import Optional, List

class StatArbSignal(BaseModel):
    """Represents an actionable Statistical Arbitrage trade signal."""
    pair_name: str           # e.g. "BTC-ETH"
    timestamp_ms: int
    asset_x: str             # e.g. "BTCUSD"
    asset_y: str             # e.g. "ETHUSD"
    asset_z: Optional[str] = None  # Optional 3rd leg
    
    current_z: float         # The current Z-score
    current_spread: float    # The raw spread value
    mean_spread: float
    std_dev: float
    
    state: str               # "armed", "active_long", "active_short", "neutral"
    action: str              # "ENTRY_LONG", "ENTRY_SHORT", "EXIT", "NONE"
    
    suggested_size_x: float
    suggested_size_y: float
    suggested_size_z: float
    
class StatArbScanResponse(BaseModel):
    """Response containing all active and actionable StatArb signals."""
    signals: List[StatArbSignal]
    count: int
    armed_count: int
    timestamp_ms: int
