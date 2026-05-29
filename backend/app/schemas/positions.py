from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from app.schemas.execution import SizedTrade
from app.schemas.directional import Direction, TradeState
from app.schemas.risk import ExitSignal
from app.schemas.greeks import GreeksSnapshot


class PositionStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


class PaperPosition(BaseModel):
    id: str
    underlying: str
    sized_trade: SizedTrade
    status: PositionStatus = PositionStatus.OPEN
    entry_timestamp_ms: int
    entry_spot_price: float
    exit_timestamp_ms: Optional[int] = None
    exit_spot_price: Optional[float] = None
    realized_pnl_usd: Optional[float] = None
    notes: str = ""
    run_once_state: TradeState = TradeState.ENTERED
    # Trailing stop / TP state
    trail_stop_json: Optional[str] = None
    trail_mode: Optional[str] = None
    entry_price_real: Optional[float] = None
    is_paper: bool = True
    # ATR-based SL/TP — persisted and auto-updated on every monitor call
    initial_sl: Optional[float] = None    # ATR-derived stop at entry (never moves)
    initial_tp: Optional[float] = None    # R:R-derived target at entry
    current_sl: Optional[float] = None    # latest trailing stop price
    current_tp: Optional[float] = None    # current take-profit price
    # Live order tracking fields (populated when algo_mode is on)
    order_id: Optional[str] = None        # Delta Exchange order ID
    order_status: Optional[str] = None   # "pending" | "filled" | "failed" | "cancelled" | "retry"
    # Trading-mode tag (scalping / intraday / swing / positional). Used to key
    # the re-entry cooldown so a scalp exit cannot block a swing entry, and
    # vice-versa. Optional for back-compat with positions persisted before this field.
    mode: Optional[str] = None

    # ── Options-specific snapshot fields (Phase 0 of the derivatives build) ──
    # All optional + back-compat with positions persisted before they existed.
    # Populated for options legs at entry, used by the corrected close_position
    # PnL math and by the background monitor's premium-aware trailing.
    entry_premium: Optional[float] = None      # debit paid per contract at entry
    exit_premium: Optional[float] = None       # mark at exit; set on close()
    entry_iv: Optional[float] = None           # IV at entry (decimal, e.g. 0.65)
    entry_dte: Optional[int] = None            # DTE at entry — used by force-close-before-expiry
    entry_greeks_snapshot: Optional[GreeksSnapshot] = None
    # Indian crypto 1% TDS — accumulates as positions close. Not used in
    # trade decisions; surfaced in UI for after-tax PnL.
    tds_withheld_usd: float = 0.0
    # Exchange-fill categorisation (matches fees.py FILL_TYPES). Set on close
    # to "normal"/"settlement"/"liquidation"/"adl"/"otc". Distinct from
    # exit_reason — fill_type is HOW the exchange categorised the closing
    # fill; exit_reason is WHY we triggered the close.
    fill_type: Optional[str] = None
    # Internal close-trigger semantics:
    #   "manual"|"stop"|"tp"|"trail"|"force_close_dte"|"signal_exit"|"liquidation"
    exit_reason: Optional[str] = None
    # True when this position crossed actual option expiry and the close was
    # a cash-settlement event (vs. a pre-expiry market close).
    settlement_recorded: bool = False


class EnterPositionRequest(BaseModel):
    underlying: str
    notes: str = ""
    structure_rank: int = 0  # 0 = top-ranked, 1 = second, etc.


class ClosePositionRequest(BaseModel):
    exit_spot_price: float
    notes: str = ""


class PositionListResponse(BaseModel):
    positions: List[PaperPosition]
    open_count: int           # open + partially_closed
    partially_closed_count: int = 0
    closed_count: int


class MonitorResult(BaseModel):
    position_id: str
    underlying: str
    exit_signal: ExitSignal
    current_spot: float
    estimated_pnl_usd: float
    current_dte: int
    current_signal_trend: int
    timestamp_ms: int


class MonitorAllResult(BaseModel):
    open_positions_checked: int
    exit_recommended: List[str]
    partial_recommended: List[str]
    results: List[MonitorResult]
    timestamp_ms: int


class PortfolioSummary(BaseModel):
    open_count: int           # fully open + partially_closed
    partially_closed_count: int = 0
    closed_count: int
    total_positions: int
    total_open_risk_usd: float
    total_realized_pnl_usd: float
    largest_open_risk_usd: float
    underlyings_open: List[str]
    avg_capital_at_risk_pct: float
    timestamp_ms: int


class TradeAnalytics(BaseModel):
    total_closed: int
    winners: int
    losers: int
    win_rate_pct: float
    avg_pnl_usd: float
    avg_winner_usd: float
    avg_loser_usd: float
    best_trade_usd: float
    worst_trade_usd: float
    total_realized_pnl_usd: float
    profit_factor: float   # gross_wins / abs(gross_losses)
    timestamp_ms: int
