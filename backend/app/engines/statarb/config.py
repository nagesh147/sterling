"""Configuration for the Statistical Arbitrage (3D Spread) Engine."""
from typing import List
from pydantic import BaseModel, Field

class StatArbPairConfig(BaseModel):
    """Configuration for a specific co-integrated pair or triad."""
    name: str = Field(default="", description="Display name for the pair")
    asset_x: str = Field(..., description="The independent asset (e.g. BTCUSD)")
    asset_y: str = Field(..., description="The dependent asset (e.g. ETHUSD)")
    
    # Optional 3rd leg for a triangular or 3D spread
    asset_z: str | None = Field(default=None, description="Optional third leg")
    
    enabled: bool = Field(default=True, description="Is this pair active?")
    hedge_ratio_y: float = Field(default=1.0, description="Hedge ratio for Y")
    hedge_ratio_z: float = Field(default=1.0, description="Hedge ratio for Z")
    
    lookback_window: int = Field(default=100, description="Rolling window for mean/stddev (e.g. 100 bars)")
    zscore_entry: float = Field(default=2.5, description="Z-score absolute value to enter a spread trade")
    zscore_exit: float = Field(default=0.5, description="Z-score absolute value to exit (mean reverted)")
    stop_loss_zscore: float = Field(default=4.0, description="Z-score to cut losses (structural break)")

class StatArbConfig(BaseModel):
    """Root configuration for the StatArb Engine."""
    enabled: bool = Field(default=False, description="Enable the Stat Arb engine globally")
    auto_trade: bool = Field(default=False, description="Hook into OrderRouter for live/shadow execution")
    timeframe: str = Field(default="5m", description="Execution timeframe for the stat arb loop")
    
    pairs: List[StatArbPairConfig] = Field(default_factory=list)
    
    lookback_bars: int = Field(default=100, description="Rolling window for mean/stddev")
    entry_z_score: float = Field(default=2.5, description="Global entry Z-score")
    exit_z_score: float = Field(default=0.5, description="Global exit Z-score")
    stop_loss_z_score: float = Field(default=4.0, description="Global stop loss Z-score")
    max_position_usd: float = Field(default=1000.0, description="Max USD to risk on one side")

def default_statarb_config() -> StatArbConfig:
    return StatArbConfig(
        enabled=True,
        auto_trade=False,
        timeframe="5m",
        lookback_bars=100,
        entry_z_score=2.5,
        exit_z_score=0.5,
        stop_loss_z_score=4.0,
        max_position_usd=1000.0,
        pairs=[
            StatArbPairConfig(
                name="BTC-ETH",
                asset_x="BTCUSD",
                asset_y="ETHUSD",
                enabled=True,
                hedge_ratio_y=0.05,
                hedge_ratio_z=1.0,
                lookback_window=100,
                zscore_entry=2.5,
                zscore_exit=0.5,
                stop_loss_zscore=4.0
            )
        ]
    )
