from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class TradeState(str, Enum):
    IDLE = "IDLE"
    EARLY_SETUP_ACTIVE = "EARLY_SETUP_ACTIVE"
    CONFIRMED_SETUP_ACTIVE = "CONFIRMED_SETUP_ACTIVE"
    FILTERED = "FILTERED"
    ENTRY_ARMED_PULLBACK = "ENTRY_ARMED_PULLBACK"
    ENTRY_ARMED_CONTINUATION = "ENTRY_ARMED_CONTINUATION"
    ENTERED = "ENTERED"
    PARTIALLY_REDUCED = "PARTIALLY_REDUCED"
    EXIT_PENDING = "EXIT_PENDING"
    EXITED = "EXITED"
    CANCELLED = "CANCELLED"


class MacroRegime(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULL_TRENDING = "bull_trending"
    BULL_WEAK = "bull_weak"
    BULL_RANGING = "bull_ranging"
    BEAR_TRENDING = "bear_trending"
    BEAR_WEAK = "bear_weak"
    BEAR_RANGING = "bear_ranging"
    CHOPPY = "choppy"
    # v2 regimes
    IDLE = "IDLE"
    VOLATILE = "VOLATILE"
    RANGING = "RANGING"
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class ExecMode(str, Enum):
    PULLBACK = "pullback"
    CONTINUATION = "continuation"
    WAIT = "wait"


class IVRBand(str, Enum):
    LOW = "low"       # < 40
    NORMAL = "normal" # 40–60
    ELEVATED = "elevated" # 60–80
    HIGH = "high"     # > 80


class RegimeResult(BaseModel):
    macro_regime: MacroRegime
    ema50: float
    close_4h: float
    score: float
    # v2 fields
    atr_percentile: float = 0.0
    adx: float = 0.0
    ema21: float = 0.0
    ema55: float = 0.0
    # v3 unified engine fields
    atr_slope: float = 0.0       # normalized: Δ(ATR/Close) over last 2 bars; negative = contracting


class SignalResult(BaseModel):
    trend: int  # 1 = bullish, -1 = bearish, 0 = neutral
    all_green: bool
    all_red: bool
    green_arrow: bool
    red_arrow: bool
    st_trends: List[int]  # [ST(7,3), ST(14,2), ST(21,1)]
    st_values: List[float]
    close_1h: float
    score_long: float
    score_short: float
    # v2 fields
    signal_strength: str = "NONE"   # "STRONG", "SIGNAL", "NONE"
    signal_score: float = 0.0       # 0-20
    rsi: float = 50.0
    squeezed: bool = False
    # v3 unified engine fields
    ha_real_divergence_pct: float = 0.0  # |Real close − HA close| / Real close * 100
    vol_confirm: bool = False             # volume > 1.5× median


class SetupResult(BaseModel):
    state: TradeState
    direction: Direction
    reason: str
    macro_regime: MacroRegime
    signal_trend: int


class PolicyResult(BaseModel):
    allowed_structures: List[str]
    ivr: Optional[float]
    ivr_band: IVRBand
    preferred_dte_min: int
    preferred_dte_max: int
    naked_allowed: bool
    debit_preferred: bool
    avoid_long_premium: bool


class ExecTimingResult(BaseModel):
    mode: ExecMode
    confidence: float
    reason: str
    exec_score: float = 0.0  # v2: 0-15 points for scoring


class DirectionalStatusResponse(BaseModel):
    underlying: str
    loaded: bool
    paper_mode: bool
    real_public_data: bool
    exchange_status: str
    has_options: bool
    regime: Optional[RegimeResult] = None
    signal: Optional[SignalResult] = None
    state: TradeState = TradeState.IDLE
    timestamp_ms: int
    atr_percentile: float = 0.0
    adx: float = 0.0


class WatchlistItem(BaseModel):
    underlying: str
    has_options: bool
    state: TradeState
    direction: Direction
    macro_regime: Optional[MacroRegime] = None
    signal_trend: Optional[int] = None
    ivr: Optional[float] = None
    ivr_band: IVRBand = IVRBand.NORMAL
    score_long: Optional[float] = None
    score_short: Optional[float] = None
    spot_price: Optional[float] = None
    daily_change_pct: Optional[float] = None  # 24h % change
    error: Optional[str] = None
    timestamp_ms: int


class WatchlistResponse(BaseModel):
    items: List[WatchlistItem]
    count: int
    timestamp_ms: int


class EvalHistoryItem(BaseModel):
    state: str
    direction: str
    recommendation: str
    no_trade_score: float
    ivr: Optional[float]
    ivr_band: Optional[str] = None
    exec_mode: Optional[str] = None      # pullback | continuation | wait
    signal_trend: Optional[int] = None   # 1=bull, -1=bear, 0=mixed
    top_structure: Optional[str] = None  # best ranked structure type
    timestamp_ms: int


class EvalHistoryResponse(BaseModel):
    underlying: str
    history: List[EvalHistoryItem]
    count: int
