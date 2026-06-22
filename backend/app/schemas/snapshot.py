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
    red_count: int = 0  # from common.exit_counter for directional/kite unification
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
    # v2 fields
    atr_percentile: float = 0.0
    adx: float = 0.0
    funding_rate: Optional[float] = None
    score_breakdown: Optional[dict] = None
    rsi: float = 50.0
    squeezed: bool = False
    # Indicator lines for charting
    st1_line: List[dict] = []
    st2_line: List[dict] = []
    st3_line: List[dict] = []
    ema50_line: List[dict] = []
    vwap_line: Optional[List[dict]] = None
