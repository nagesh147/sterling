from pydantic import BaseModel
from typing import Optional, List
from app.schemas.directional import TradeState, Direction, ExecMode, IVRBand


class CandidateContract(BaseModel):
    instrument_name: str
    underlying: str
    strike: float
    expiry_date: str
    dte: int
    option_type: str
    bid: float
    ask: float
    mark_price: float
    mid_price: float
    mark_iv: float
    delta: float
    open_interest: float
    volume_24h: float
    spread_pct: float
    health_score: float
    healthy: bool
    health_veto_reason: Optional[str] = None


class TradeStructure(BaseModel):
    structure_type: str  # "naked_call","naked_put","bull_call_spread","bear_put_spread","bull_put_spread","bear_call_spread"
    direction: Direction
    legs: List[CandidateContract]
    max_loss: Optional[float]
    max_gain: Optional[float]
    net_premium: float
    risk_reward: Optional[float]
    score: float
    score_breakdown: dict


class SizedTrade(BaseModel):
    structure: TradeStructure
    contracts: int
    position_value: float
    max_risk_usd: float
    capital_at_risk_pct: float


class RunOnceResponse(BaseModel):
    underlying: str
    paper_mode: bool
    state: TradeState
    direction: Direction
    regime: Optional[dict] = None
    signal: Optional[dict] = None
    exec_mode: ExecMode = ExecMode.WAIT
    ivr: Optional[float] = None
    ivr_band: IVRBand = IVRBand.NORMAL
    ranked_structures: List[SizedTrade] = []
    no_trade_score: float = 0.0
    recommendation: str = ""
    reason: str = ""
    timestamp_ms: int = 0


class PreviewResponse(BaseModel):
    underlying: str
    state: TradeState
    direction: Direction
    candidates: List[CandidateContract] = []
    ranked_structures: List[TradeStructure] = []
    ivr: Optional[float] = None
    ivr_band: IVRBand = IVRBand.NORMAL
    reason: str = ""
    timestamp_ms: int = 0
