"""API/UI pydantic models for the Kite Sterling Kite Engine."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

from app.engines.sterling_kite_engine.config import ExitMode
from app.engines.navigator.schemas import NavigatorDecision  # noqa: F401 — used in EngineSignalRow.navigator


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
    premium_spot: Optional[float] = None   # entry premium (fill reference) — the Entry column
    premium_sl: Optional[float] = None     # live ratcheting trail stop — the TSL column
    entry_sl: Optional[float] = None       # initial hard stop at the entry bar (fast ST line) — the SL column
    token: Optional[int] = None
    is_active: bool = False   # this contract's SuperTrend is still aligned on the latest bar
    # Contract-local evidence. The grouped parent is a display/sort summary only.
    signal_timestamp_ms: Optional[int] = None
    entry_timestamp_ms: Optional[int] = None
    alignment: Optional[AlignmentChip] = None
    exit_state: Optional[str] = None


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
    stop_loss: float          # live ratcheting trail stop (underlying pts for spot/confluence) — TSL column
    # Initial hard stop at the entry bar = the validated fast ST line at the trigger.
    # Underlying pts for spot/confluence rows; premium for derivatives (leg-level too).
    # None for legacy cached rows. Surfaced as the signal table's SL column.
    entry_sl: Optional[float] = None
    # Live red-counter progress at the latest bar, "<reds>/<threshold> red" (threshold
    # from exit_mode). The Exit column; None for legacy cached rows.
    exit_state: Optional[str] = None
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
    # "derivatives" = SuperTrend on this contract's OWN premium chart (single leg, BUY-only);
    # "confluence" = underlying fired AND the leg's own premium confirmed (merged row).
    source: Literal["spot", "derivatives", "confluence"] = "spot"
    # Trend-quality readings at the entry bar (for the optional directional-mode
    # entry filters). None when not computed; never gates anything unless adx_min /
    # atr_pct_min are set in the engine config.
    adx: Optional[float] = None
    atr_pct: Optional[float] = None
    # Sterling Value-Flow Navigator (optional, off by default). None when
    # Navigator is disabled for this user, or before it has evidence for
    # this row. Never changes `score`/`source`/`is_active`/`is_fresh` above —
    # those remain exactly as the base engine computed them. Old cached rows
    # without this field deserialize fine (defaults to None).
    navigator: Optional["NavigatorDecision"] = None


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
    exit_mode: str = "one_red"  # the exit counter rule active when this position was opened (remembers choice for display + audit)
    current_red_count: int = 0
    exit_threshold: int = 1  # 1/2/3 based on exit_mode at last update; used for health display


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
    exit_mode: str = "two_red"  # for viz of current exit threshold


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
    # True only during NSE/BSE session. When auto_scan is on but the market is
    # closed the loop intentionally pauses, so next_scan_ms goes stale — the UI
    # uses this to say "market closed" instead of a misleading "next due now".
    market_open: bool = True


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
    # Master gate. True (default) = Sterling Kite Engine active (scanning,
    # signals, auto-execute). False = engine OFF; the Kite platform runs as normal
    # (manual trading only). Toggled from the Connect tab.
    engine_enabled: bool = True
    # Which ST line trails the stop. "fast" (tightest band) is the most OOS-robust
    # exit in the 7.5y sweep and bleeds the least theta; "mid"/"slow" stay selectable.
    trail_target: Literal["fast", "mid", "slow"] = "fast"
    # ── Auto-exit mode ────────────────────────────────────────────────────────
    # Controls how many red SuperTrend lines trigger auto-exit:
    #   one_red          — ANY one line red → exit (tightest, default/legacy)
    #   two_red          — any TWO lines red → exit
    #   three_red        — ALL THREE lines red → exit (full reversal)
    #   three_red_signal — all three red AND a fresh counter-arrow → exit (loosest)
    # MEASURED best on real 7.5y IS/OOS (study/kite_st_exit_mode_sweep.py): one_red
    # beats two_red/three_red on both delta1 and options lenses (see config.py). Was
    # "two_red" (asserted, never measured). Looser modes stay selectable.
    exit_mode: ExitMode = "one_red"
    # Opt-in: anchor the price stop to the exit_mode-th ST line (one_red→fast,
    # two_red→mid, three_red→slow) so the stop breach coincides with the red count
    # instead of the tightest line pre-empting it. OFF (default) = validated fast trail.
    exit_aligned_trail: bool = False
    # multi-select: scan resolves a leg for EACH selected moneyness (ITM into the
    # money, OTM out of the money). Defaults to the full ATM→ITM→OTM ladder.
    strike_moneyness: List[Literal["ATM", "ITM1", "ITM2", "ITM3", "ITM4", "ITM5", "OTM1", "OTM2", "OTM3", "OTM4", "OTM5"]] = [
        "ITM1", "ATM", "OTM1"]
    # Where the SuperTrend runs: "spot" = underlying chart (legs are candidate strikes);
    # "derivatives" = each selected contract's own premium chart (BUY-only); "both".
    # Default "spot": it is the only source with an OOS-durable edge in the 7.5y study
    # (delta-1 OOS-positive on 4/4 indices), gives both directions, and is now fully
    # stop-protected (delta-translated premium stop). Premium-chart ("derivatives")
    # signals are unvalidated and structurally unvalidatable over history; keep that
    # mode for confirmation/manual use. "both" runs both but auto-exec then guards
    # per-underlying to avoid stacking the same move (see service._make_place_cb).
    # "confluence" = highest conviction: emit a strike only when the underlying fires a
    # fresh entry AND that option's own premium ST also confirms (merged row).
    scan_source: Literal["spot", "derivatives", "both", "confluence"] = "spot"
    # Option expiries to scan — weekly, monthly, or both. Defaults to all.
    scan_expiries: List[Literal["weekly", "monthly"]] = ["weekly", "monthly"]
    # Per-category override: indices may be weekly/monthly; single-stock
    # derivatives are exchange-listed monthly contracts only.
    scan_expiries_indices: Optional[List[Literal["weekly", "monthly"]]] = None
    scan_expiries_stocks: Optional[List[Literal["monthly"]]] = ["monthly"]
    # Granular universe selection — applied to BOTH the spot and derivatives scans.
    # Indices are kept by display name; stocks by name, unless scan_all_stocks is set.
    scan_indices: List[str] = ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE", "SENSEX"]
    scan_stocks: List[str] = []
    scan_all_stocks: bool = False  # default preserves the full spot universe
    auto_execute: bool = False
    # ── Per-trade risk sizing (workstream F) ──────────────────────────────────
    # When on, auto-exec sizes lots so premium-at-risk ((entry − stop) × qty) stays
    # within risk_pct% of available FO capital, floored at 1 lot and capped by
    # max_lots and affordable margin. When off, falls back to a single lot.
    risk_sizing: bool = True
    risk_pct: float = 1.0          # % of available FO capital risked per trade
    max_lots: int = 10             # hard ceiling on auto-exec lots per order
    # ── Expiry square-off guard ────────────────────────────────────────────────
    # Market-exit an auto-exec option position when its contract comes within this
    # many calendar days of expiry, so a weekly can't ride into expiry unmanaged
    # (median signal hold ≈ 3.7d, p90 ≈ 10d, vs a weekly's ~5 sessions). 0 disables.
    # Applies to options only (futures roll rather than square off → empty expiry).
    expiry_square_off_days: int = 1
    # ── Time-stop (opt-in, default off) ────────────────────────────────────────
    # Square off an auto-exec position after it has been held this many 1H bars.
    # The exit-mechanics sweep (study/kite_st_exit_sweep.py, real 7.5y) found a
    # ~48-bar cap is the one robust, cross-lens improvement — it curbs theta bleed on
    # long-option holds (options-lens mean OOS −134% → −32%). Default 0 = off, because
    # the sweep's IS→OOS rank corr is negative (specific configs overfit) and the
    # delta-1 benefit is marginal; it mainly helps the long-OTM-options vehicle. 0 = off.
    time_stop_bars: int = 0
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
    # ── Session / liquidity entry gates (auto-exec; opt-in, default off) ──────
    # Block NEW auto-exec entries in the last N minutes before the 15:30 close so a
    # fresh late-session signal doesn't enter straight into an overnight index gap
    # (there is no INR daily-loss breaker behind an overnight hold). 0 = off.
    block_entry_minutes_before_close: int = 0
    # Skip an auto-exec entry whose chosen option leg is too illiquid to trade well:
    # bid-ask spread wider than this % of mid, or open interest below this floor.
    # None = off (the scanner itself makes no quote calls; these add one at entry).
    max_spread_pct: Optional[float] = None   # e.g. 5.0 → reject > 5% quoted spread
    min_oi: Optional[int] = None             # e.g. 100 → reject thin strikes
    # ── INR daily-loss breaker (auto-exec; opt-in, default off) ───────────────
    # Halt NEW auto-exec entries once realized losses for the IST day reach this % of
    # available F&O capital. Fills the gap left by the USD daily-loss breaker being
    # crypto-only. None = off. Only ever blocks entries; never force-closes.
    max_daily_loss_pct: Optional[float] = None
    # ── Risk infrastructure wiring ────────────────────────────────────────────
    # Wires the drawdown circuit breaker + correlation penalty into sizing.
    wire_risk_infra: bool = False
    # ── Hybrid trail weight (for ATR+ST hybrid trailing in unified exit logic) ─
    # 0 = pure ATR, 1 = pure ST lines, 0.5 = balanced blend. Used when trail_mode=hybrid.
    hybrid_st_weight: float = 0.5

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

    @field_validator("scan_expiries_stocks", mode="before")
    @classmethod
    def _stocks_are_monthly_only(cls, v):
        # Accept stale clients/saved configs but never preserve an invented weekly
        # single-stock series in the validated API model.
        return ["monthly"]

    @field_validator("target_delta")
    @classmethod
    def _target_delta_bounds(cls, v):
        if v is None:
            return v
        # Any delta in (0,1) is a valid option strike target. OTM buys sit ~0.20–0.45,
        # ATM ~0.50, deep-ITM ~0.80+. The resolver (pick_by_delta) simply picks the
        # nearest strike, so the full band is allowed.
        return min(0.99, max(0.05, float(v)))

    @field_validator("hybrid_st_weight")
    @classmethod
    def _hybrid_weight_bounds(cls, v):
        if v is None:
            return v
        return min(1.0, max(0.0, float(v)))

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
    trail_target: Literal["fast", "mid", "slow"] = "fast"
    # Exit counter (how many red ST lines trigger the exit), mirrors the live engine.
    # The backtest exit IS this red-count rule; trail_target is retained for the live
    # stop level but does not change the backtest exit.
    exit_mode: ExitMode = "two_red"
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
