from pydantic import BaseModel
from typing import Optional, List


class AssetBalance(BaseModel):
    asset: str
    available: float
    locked: float
    total: float
    usd_value: Optional[float] = None


class AccountPosition(BaseModel):
    symbol: str
    underlying: str
    size: float          # positive = long, negative = short
    side: str            # "long" | "short"
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    realized_pnl: float
    margin: float
    leverage: Optional[float] = None
    position_type: str   # "options" | "perpetual" | "futures"
    created_at_ms: Optional[int] = None


class AccountOrder(BaseModel):
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    filled_size: float = 0.0
    status: str          # "open" | "filled" | "cancelled"
    order_type: str      # "limit" | "market"
    created_at_ms: int


class AccountFill(BaseModel):
    fill_id: str
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    fee: float
    fee_asset: str
    pnl: float = 0.0
    created_at_ms: int


class PortfolioSnapshot(BaseModel):
    exchange: str
    display_name: str
    total_balance_usd: float
    unrealized_pnl_usd: float
    realized_pnl_usd: float
    margin_used: float
    margin_available: float
    positions_count: int
    open_orders_count: int
    balances: List[AssetBalance]
    timestamp_ms: int


class AccountSummaryResponse(BaseModel):
    exchange_id: str
    exchange_name: str
    display_name: str
    is_paper: bool
    is_connected: bool
    portfolio: Optional[PortfolioSnapshot] = None
    error: Optional[str] = None
    timestamp_ms: int
