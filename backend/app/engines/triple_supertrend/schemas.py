"""API/UI pydantic models for the Kite triple-SuperTrend engine."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator


class AlignmentChip(BaseModel):
    fast: int  # +1 / -1 / 0
    mid: int
    slow: int


class OptionLeg(BaseModel):
    moneyness: str  # ATM / ITM1-5 / OTM1-5
    option_type: str  # CE / PE
    option_symbol: str
    strike: float
    expiry: str
    lot_size: Optional[int] = None
    premium_spot: Optional[float] = None
    premium_sl: Optional[float] = None
    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar


class EngineSignalRow(BaseModel):
    underlying: str
    token: int
    exchange: str  # option exchange (NFO / BFO)
    regime: Literal["BULL", "BEAR"]
    alignment: AlignmentChip
    direction: Literal["long", "short"]
    option_type: Literal["CE", "PE"]
    legs: List[OptionLeg] = []  # one per selected moneyness (ATM/ITM1-5/OTM1-5)
    spot: float
    stop_loss: float
    score: float
    timestamp_ms: int
    # is_active = the SuperTrend is STILL aligned on the latest closed bar (trade is
    # running), vs. a stale entry whose trend has since broken. is_fresh = entered on
    # the latest bar (the live "ready now" trigger). For grouped derivative rows these
    # are OR'd across the legs; per-contract liveness is on each OptionLeg.is_active.
    is_active: bool = False
    is_fresh: bool = False
    # "spot" = SuperTrend on the underlying chart (legs are candidate strikes to BUY);
    # "derivatives" = SuperTrend on this contract's OWN premium chart (single leg, BUY-only).
    source: Literal["spot", "derivatives"] = "spot"


class SignalsResponse(BaseModel):
    generated_ms: int
    scanning: bool
    scanning_label: str = ""
    rows: List[EngineSignalRow]
    next_scan_ms: int = 0
    auto_scan: bool = False
    market_open: bool = True


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
    scanning_label: str = ""


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
    strike_moneyness: List[Literal["ATM", "ITM1", "ITM2", "ITM3", "ITM4", "ITM5", "OTM1", "OTM2", "OTM3", "OTM4", "OTM5"]] = [
        "ITM1", "ATM", "OTM1"]
    # Where the SuperTrend runs: "spot" = underlying chart (legs are candidate strikes);
    # "derivatives" = each selected contract's own premium chart (BUY-only); "both".
    scan_source: Literal["spot", "derivatives", "both"] = "derivatives"
    # Option expiries to scan — weekly, monthly, or both. Defaults to all.
    scan_expiries: List[Literal["weekly", "monthly"]] = ["weekly", "monthly"]
    # Per-category override: indices (default both), stocks (default monthly only).
    scan_expiries_indices: Optional[List[Literal["weekly", "monthly"]]] = None
    scan_expiries_stocks: Optional[List[Literal["weekly", "monthly"]]] = None
    # Granular universe selection — applied to BOTH the spot and derivatives scans.
    # Indices are kept by display name; stocks by name, unless scan_all_stocks is set.
    scan_indices: List[str] = ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE", "SENSEX"]
    scan_stocks: List[str] = []
    scan_all_stocks: bool = False  # default preserves the full spot universe
    early_lock: bool = False
    auto_execute: bool = False

    @field_validator("strike_moneyness")
    @classmethod
    def _at_least_one_moneyness(cls, v):
        return v or ["ITM1", "ATM", "OTM1"]

    @field_validator("scan_expiries")
    @classmethod
    def _at_least_one_expiry(cls, v):
        return v or ["weekly", "monthly"]


# ── Per-contract scan report ─────────────────────────────────────────────────
class ContractScanEntry(BaseModel):
    underlying: str
    symbol: str          # option tradingsymbol
    strike: float
    option_type: Literal["CE", "PE"]
    expiry: str          # YYYY-MM-DD
    moneyness: str       # ATM/ITM1-5/OTM1-5
    bars: int            # premium bars available
    premium_close: float # last premium close (0 if no candles)
    fired: bool          # produced a BUY signal on the latest bar
    fired_at_ms: int = 0 # timestamp of the fired entry (0 if not fired)
    reason: str          # "fresh BUY signal" | "no up-transition" (bars>warmup) | "too few bars" | "no data" | "expired"


class ScanReportSummary(BaseModel):
    generated_ms: int
    scan_source: str
    indices: List[str]
    total_contracts: int
    charted: int         # contracts with premium candle data
    fired: int           # contracts that produced a fresh BUY signal
    no_data: int         # contracts skipped (no token/empty fetch)
    min_bars: int
    max_bars: int
    total_ce: int
    total_pe: int
    fired_ce: int
    fired_pe: int


class ScanReportResponse(BaseModel):
    summary: ScanReportSummary
    entries: List[ContractScanEntry]
