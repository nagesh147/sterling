from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from app.schemas.execution import SizedTrade
from app.schemas.directional import Direction, TradeState
from app.schemas.risk import ExitSignal


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


class EnterPositionRequest(BaseModel):
    underlying: str
    notes: str = ""
    structure_rank: int = 0  # 0 = top-ranked, 1 = second, etc.


class ClosePositionRequest(BaseModel):
    exit_spot_price: float
    notes: str = ""


class PositionListResponse(BaseModel):
    positions: List[PaperPosition]
    open_count: int
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
    open_count: int
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
