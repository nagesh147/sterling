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
    structure_type: str  # "naked_call","naked_put","bull_call_spread","bear_put_spread",
                         # "bull_put_spread","bear_call_spread","futures"
    direction: Direction
    legs: List[CandidateContract]
    max_loss: Optional[float]
    max_gain: Optional[float]
    net_premium: float
    risk_reward: Optional[float]
    score: float
    score_breakdown: dict
    leverage: int = 1               # futures leverage; 1 for options
    entry_price: Optional[float] = None  # spot price snapshot for futures


class SizedTrade(BaseModel):
    structure: TradeStructure
    contracts: float
    position_value: float
    max_risk_usd: float
    capital_at_risk_pct: float
    # Size of ONE exchange contract in the underlying (Delta India perps:
    # BTC=0.001, ETH=0.01, SOL=1). `contracts` counts whole exchange lots;
    # the actual coin quantity is contracts * contract_value. Defaults to 1.0
    # so every legacy path (options, directional, manual) — where `contracts`
    # has always meant whole coins — keeps its exact prior value/risk/PnL math.
    contract_value: float = 1.0
    # TTACE Phase 3: populated when the sizer fails closed (cold-start /
    # unknown edge / kelly<=0). Defaults to None when sized normally.
    blocked_reason: Optional[str] = None

    @property
    def qty(self) -> float:
        """Coin quantity this position represents = lots * lot size. Use this
        (never raw `contracts`) for value / risk / PnL; `contracts` alone is the
        exchange order size (lot count)."""
        return self.contracts * self.contract_value


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
    score_breakdown: Optional[dict] = None
    funding_rate: Optional[float] = None
    # B5: MTF (multi-timeframe) score decomposition exposed for UI consumption.
    # macro_4h: regime score (0-20)
    # signal_1h: 1H confluence score (0-20)
    # execution_15m: pullback/continuation score (0-15)
    # alignment: human-readable alignment label
    mtf_breakdown: Optional[dict] = None


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
