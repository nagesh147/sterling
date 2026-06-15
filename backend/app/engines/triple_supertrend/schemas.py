"""API/UI pydantic models for the Kite triple-SuperTrend engine."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator


class AlignmentChip(BaseModel):
    fast: int  # +1 / -1 / 0
    mid: int
    slow: int


class OptionLeg(BaseModel):
    moneyness: str  # ATM / ITM1 / ITM2 / OTM1 / OTM2
    option_type: str  # CE / PE
    option_symbol: str
    strike: float
    expiry: str
    lot_size: Optional[int] = None


class EngineSignalRow(BaseModel):
    underlying: str
    token: int
    exchange: str  # option exchange (NFO / BFO)
    regime: Literal["BULL", "BEAR"]
    alignment: AlignmentChip
    direction: Literal["long", "short"]
    option_type: Literal["CE", "PE"]
    legs: List[OptionLeg] = []  # one per selected moneyness (ATM/ITM1/ITM2/OTM1/OTM2)
    spot: float
    stop_loss: float
    score: float
    timestamp_ms: int
    # "spot" = SuperTrend on the underlying chart (legs are candidate strikes to BUY);
    # "derivatives" = SuperTrend on this contract's OWN premium chart (single leg, BUY-only).
    source: Literal["spot", "derivatives"] = "spot"


class SignalsResponse(BaseModel):
    generated_ms: int
    scanning: bool
    rows: List[EngineSignalRow]
    next_scan_ms: int = 0
    auto_scan: bool = False


class SetupPoint(BaseModel):
    time: int  # epoch seconds (lightweight-charts)
    open: float
    high: float
    low: float
    close: float


class SetupLine(BaseModel):
    time: int  # epoch seconds
    value: float


class SetupChart(BaseModel):
    underlying: str
    candles: List[SetupPoint]  # Heikin-Ashi candles
    st_fast: List[SetupLine]
    st_mid: List[SetupLine]
    st_slow: List[SetupLine]
    entry_index: Optional[int] = None  # bar index of the fresh transition
    trail_target: str


class ActivityEvent(BaseModel):
    ts_ms: int
    kind: str  # scan_start | scan_done | order_placed | order_blocked | order_failed | error | info
    message: str


class ActivityResponse(BaseModel):
    events: List[ActivityEvent]
    scanning: bool
    auto_scan: bool
    last_scan_ms: int
    next_scan_ms: int
    signal_count: int


class DepthLevel(BaseModel):
    price: float
    quantity: int
    orders: int


class OptionDetail(BaseModel):
    moneyness: str
    option_type: str
    option_symbol: str
    strike: float
    expiry: str
    lot_size: Optional[int] = None
    dte: int = 0
    last_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    iv: float = 0.0  # decimal (0.18 = 18%)
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    depth_buy: List[DepthLevel] = []
    depth_sell: List[DepthLevel] = []


class EngineDetailResponse(BaseModel):
    underlying: str
    token: int
    exchange: str  # option exchange (NFO/BFO)
    direction: Literal["long", "short"]
    regime: Literal["BULL", "BEAR"]
    alignment: AlignmentChip
    option_type: Literal["CE", "PE"]
    triggered_ms: int
    spot_at_trigger: float
    spot_now: float
    stop_loss: float
    options: List[OptionDetail]


class EngineOrderRequest(BaseModel):
    option_symbol: str
    exchange: str  # NFO / BFO
    side: Literal["BUY", "SELL"]
    quantity: int
    order_type: str = "MARKET"
    product: str = "NRML"


class EngineOrderResponse(BaseModel):
    order_id: str
    status: str  # ok | duplicate
    message: str


class HistorySignal(BaseModel):
    """A past entry transition found by replaying the engine over a date window."""
    ts_ms: int
    underlying: str
    source: Literal["spot", "derivatives"]
    direction: Literal["long", "short"]
    option_type: Literal["CE", "PE"]
    option_symbol: str = ""   # derivatives only
    moneyness: str = ""       # derivatives only
    entry_price: float
    stop_loss: float
    is_now: bool = False      # fresh entry on the latest closed bar (the live "ready" signal)


class HistoryResponse(BaseModel):
    generated_ms: int
    from_ms: int
    to_ms: int
    scan_source: str
    signals: List[HistorySignal]


class EngineConfigModel(BaseModel):
    trail_target: Literal["fast", "mid", "slow"] = "mid"
    # multi-select: scan resolves a leg for EACH selected moneyness (ITM into the
    # money, OTM out of the money). Defaults to the full ATM→ITM→OTM ladder.
    strike_moneyness: List[Literal["ATM", "ITM1", "ITM2", "OTM1", "OTM2"]] = [
        "ITM1", "ATM", "OTM1"]
    # Where the SuperTrend runs: "spot" = underlying chart (legs are candidate strikes);
    # "derivatives" = each selected contract's own premium chart (BUY-only); "both".
    scan_source: Literal["spot", "derivatives", "both"] = "derivatives"
    # Granular universe selection — applied to BOTH the spot and derivatives scans.
    # Indices are kept by display name; stocks by name, unless scan_all_stocks is set.
    scan_indices: List[str] = ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE", "SENSEX"]
    scan_stocks: List[str] = []
    scan_all_stocks: bool = False  # default preserves the full spot universe
    early_lock: bool = False
    auto_execute: bool = False

    @field_validator("strike_moneyness")
    @classmethod
    def _at_least_one(cls, v):
        return v or ["ITM1", "ATM", "OTM1"]
