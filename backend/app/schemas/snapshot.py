from pydantic import BaseModel
from typing import List, Optional
from app.schemas.directional import TradeState, IVRBand


class DirectionalSnapshot(BaseModel):
    underlying: str
    spot_price: float
    perp_price: float
    # Regime
    macro_regime: str
    ema50: float
    regime_score: float
    # Signal
    signal_trend: int
    all_green: bool
    all_red: bool
    green_arrow: bool
    red_arrow: bool
    st_trends: List[int]
    st_values: List[float]
    score_long: float
    score_short: float
    close_1h: float
    # Options context
    ivr: Optional[float]
    ivr_band: IVRBand
    # Setup
    state: TradeState
    direction: str
    setup_reason: str
    # Execution timing
    exec_mode: str
    exec_confidence: float
    exec_reason: str
    timestamp_ms: int
