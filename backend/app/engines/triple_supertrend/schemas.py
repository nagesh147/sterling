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
    # Underlying spot at the trigger bar. For "spot"-source signals this equals
    # ``spot``; for "derivatives" signals ``spot`` carries the option premium (and is
    # zeroed during leg grouping), so the underlying spot is captured separately here
    # from the underlying's 1H candle at the trigger timestamp. None when the
    # underlying candle for that bar wasn't available.
    underlying_spot: Optional[float] = None
    # is_active = the SuperTrend is STILL aligned on the latest closed bar (trade is
    # running), vs. a stale entry whose trend has since broken. is_fresh = entered on
    # the latest bar (the live "ready now" trigger). For grouped derivative rows these
    # are OR'd across the legs; per-contract liveness is on each OptionLeg.is_active.
    is_active: bool = False
    is_fresh: bool = False
    # "spot" = SuperTrend on the underlying chart (legs are candidate strikes to BUY);
    # "derivatives" = SuperTrend on this contract's OWN premium chart (single leg, BUY-only).
    source: Literal["spot", "derivatives"] = "spot"
    # Trend-quality readings at the entry bar (for the optional directional-mode
    # entry filters). None when not computed; never gates anything unless adx_min /
    # atr_pct_min are set in the engine config.
    adx: Optional[float] = None
    atr_pct: Optional[float] = None


class SignalsResponse(BaseModel):
    generated_ms: int
    scanning: bool
    scanning_label: str = ""
    rows: List[EngineSignalRow]
    next_scan_ms: int = 0
    auto_scan: bool = False
    market_open: bool = True


class OpenPositionRecord(BaseModel):
    symbol: str
    exchange: str
    token: int = 0
    qty: int = 0
    lot_size: int = 0
    entry_premium: float = 0.0
    fill_price: float = 0.0
    stop_premium: float = 0.0
    status: str = ""
    direction: str = "long"
    vehicle: str = "otm_options"
    underlying: str = ""
    opened_ms: int = 0
    exit_reason: str = ""
    order_id: str = ""


class OpenPositionsResponse(BaseModel):
    positions: List[OpenPositionRecord]


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


Vehicle = Literal["otm_options", "deep_itm_options", "futures"]
DeepItmMoneyness = Literal["ITM5", "ITM10", "ITM15", "ITM20"]


class EngineConfigModel(BaseModel):
    # Master gate. True (default) = Triple-SuperTrend engine active (scanning,
    # signals, auto-execute). False = engine OFF; the Kite platform runs as normal
    # (manual trading only). Toggled from the Connect tab.
    engine_enabled: bool = True
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
    # ── Per-trade risk sizing (workstream F) ──────────────────────────────────
    # When on, auto-exec sizes lots so premium-at-risk ((entry − stop) × qty) stays
    # within risk_pct% of available FO capital, floored at 1 lot and capped by
    # max_lots and affordable margin. When off, falls back to a single lot.
    risk_sizing: bool = True
    risk_pct: float = 1.0          # % of available FO capital risked per trade
    max_lots: int = 10             # hard ceiling on auto-exec lots per order
    # ── Protective stop mode (workstreams C/D) ────────────────────────────────
    # "broker"  = place a GTT/SL-M stop at Zerodha at entry (survives server death)
    # "monitor" = tick-driven WS monitor exits on trail breach (intrabar, server-side)
    # "both"    = both (default; defense in depth for real money)
    stop_mode: Literal["broker", "monitor", "both"] = "both"

    # ── Directional mode (additive, opt-in) ───────────────────────────────────
    # Master toggle. False ⇒ existing engine, untouched (byte-identical).
    # True ⇒ monetize the signal through the selected vehicle instead.
    directional_mode: bool = False
    # Which vehicle to trade when directional_mode is ON.
    # otm_options = existing behavior; deep_itm_options = high-delta ITM;
    # futures = index futures (delta-1, two-sided).
    vehicle: Vehicle = "otm_options"
    # Which vehicles the user has enabled (checkboxes in the UI). The active
    # `vehicle` must be in this set. Futures is opt-in — default is options only.
    enabled_vehicles: List[Vehicle] = ["otm_options", "deep_itm_options"]
    # ── Deep-ITM options config ───────────────────────────────────────────────
    # How many strike steps into the money (ITM5 / ITM10 / ITM15 / ITM20).
    itm_depth: Optional[DeepItmMoneyness] = "ITM10"
    # Alternatively, pick the strike nearest to a target BS delta (overrides itm_depth).
    target_delta: Optional[float] = None   # e.g. 0.90 for ~delta-0.9
    # ── Futures config ────────────────────────────────────────────────────────
    futures_expiry: Literal["near", "next"] = "near"
    # ── Entry quality filters (Phase-0 survivors; None = off) ─────────────────
    adx_min: Optional[float] = None          # minimum ADX to allow entry (e.g. 20)
    atr_pct_min: Optional[float] = None      # minimum ATR percentile (e.g. 50)
    # ── Risk infrastructure wiring ────────────────────────────────────────────
    # Wires the drawdown circuit breaker + correlation penalty into sizing.
    wire_risk_infra: bool = False

    @field_validator("risk_pct")
    @classmethod
    def _risk_pct_bounds(cls, v):
        # Clamp to a sane 0.1%–25% band; 0/negative would size to nothing.
        return min(25.0, max(0.1, float(v)))

    @field_validator("max_lots")
    @classmethod
    def _max_lots_bounds(cls, v):
        return min(500, max(1, int(v)))

    @field_validator("strike_moneyness")
    @classmethod
    def _at_least_one_moneyness(cls, v):
        return v or ["ITM1", "ATM", "OTM1"]

    @field_validator("scan_expiries")
    @classmethod
    def _at_least_one_expiry(cls, v):
        return v or ["weekly", "monthly"]

    @field_validator("target_delta")
    @classmethod
    def _target_delta_bounds(cls, v):
        if v is None:
            return v
        # Any delta in (0,1) is a valid option strike target. OTM buys sit ~0.20–0.45,
        # ATM ~0.50, deep-ITM ~0.80+. The resolver (pick_by_delta) simply picks the
        # nearest strike, so the full band is allowed.
        return min(0.99, max(0.05, float(v)))

    @field_validator("adx_min")
    @classmethod
    def _adx_bounds(cls, v):
        if v is None:
            return v
        return min(50.0, max(5.0, float(v)))

    @field_validator("atr_pct_min")
    @classmethod
    def _atr_pct_bounds(cls, v):
        if v is None:
            return v
        return min(95.0, max(10.0, float(v)))


# ── Options backtest (workstream H) ──────────────────────────────────────────
class BacktestRequest(BaseModel):
    # What to test. For synthetic/both, the symbol is the UNDERLYING (e.g.
    # "NIFTY 50"); for real, it is an option tradingsymbol (e.g. "NIFTY24JUN24000CE").
    symbol: str
    data_mode: Literal["synthetic", "real", "both"] = "both"
    trail_target: Literal["fast", "mid", "slow"] = "mid"
    lookback_bars: int = 2000          # 1H bars (synthetic can reach back years)
    starting_capital: float = 100_000.0
    qty: int = 50                      # one lot (lot_size) — value/risk scales with this
    # Synthetic-only knobs:
    iv: float = 0.18                   # fixed IV assumption for BS pricing (decimal)
    dte_days: float = 7.0              # weekly option horizon at entry
    moneyness_offset_pct: float = 0.0  # 0 = ATM; +ve = OTM, signed by direction
    # Cost overrides (None = schedule defaults):
    slippage_pct: Optional[float] = None
    brokerage_per_order: Optional[float] = None

    @field_validator("lookback_bars")
    @classmethod
    def _bars_bounds(cls, v):
        return min(10_000, max(100, int(v)))


class BacktestTradeModel(BaseModel):
    entry_ms: int
    exit_ms: int
    direction: str
    entry_premium: float
    exit_premium: float
    qty: int
    gross_pnl: float
    costs: float
    net_pnl: float
    bars_held: int
    exit_reason: str


class BacktestStatsModel(BaseModel):
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    gross_pnl: float = 0.0
    total_costs: float = 0.0
    net_pnl: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    return_pct: float = 0.0
    final_capital: float = 0.0


class BacktestRunModel(BaseModel):
    mode: str
    caveat: str = ""
    trades: List[BacktestTradeModel] = []
    equity_curve: List[float] = []
    stats: BacktestStatsModel


class BacktestResponse(BaseModel):
    symbol: str
    data_mode: str
    generated_ms: int
    runs: List[BacktestRunModel]          # one per executed mode (synthetic / real)
    # When data_mode="both": mean abs % drift of the live contract's modeled-vs-real
    # premium (a calibration sanity check on the synthetic assumption).
    bs_vs_real_drift_pct: Optional[float] = None
    notes: List[str] = []


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
