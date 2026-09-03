"""Data models for Bear to Bearish Strategy Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BearToBearishConfig(BaseModel):
    """Configuration options for Bear to Bearish engine."""
    enabled: bool = True
    pcr_threshold: float = Field(default=0.60, description="PCR ceiling for bearish confirmation (below 0.60)")
    pcr_reversal_jump: float = Field(default=0.20, description="PCR jump points within 5-10m window triggering invalidation")
    timeframe: str = Field(default="5m", description="Timeframe for Lower High detection (1m, 3m, 5m)")
    auto_execute: bool = Field(default=False, description="Enable automatic order submission via OrderRouter")
    max_risk_inr: float = Field(default=5000.0, description="Max INR risk per trade")
    scan_indices: List[str] = Field(default_factory=lambda: ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"])


@dataclass
class PcrPoint:
    timestamp_ms: int
    pcr: float
    volume_pcr: float = 0.0
    change_oi_pcr: float = 0.0
    index_close: float = 0.0


@dataclass
class BearToBearishSignal:
    id: str
    underlying: str
    symbol: str
    exchange: str
    direction: str = "short"
    status: str = "armed"  # armed | running | weakening | ended | watching | error
    timestamp_ms: int = 0
    pcr_open: float = 0.80
    pcr_current: float = 0.58
    pcr_change_5m: float = -0.05
    lower_high_price: float = 0.0
    spot_price: float = 0.0
    spot_sl: float = 0.0
    spot_target: float = 0.0
    option_premium: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    score: int = 85
    reason: Optional[str] = None
    option_type: str = "PE"
    strike: Optional[float] = None
    expiry: Optional[str] = None
    lot_size: int = 25
    quote_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "underlying": self.underlying,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "direction": self.direction,
            "status": self.status,
            "timestamp_ms": self.timestamp_ms,
            "pcr_open": self.pcr_open,
            "pcr_current": self.pcr_current,
            "pcr_change_5m": self.pcr_change_5m,
            "lower_high_price": self.lower_high_price,
            "spot_price": self.spot_price,
            "spot_sl": self.spot_sl,
            "spot_target": self.spot_target,
            "option_premium": self.option_premium,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
            "score": self.score,
            "reason": self.reason,
            "option_type": self.option_type,
            "strike": self.strike,
            "expiry": self.expiry,
            "lot_size": self.lot_size,
            "quote_key": self.quote_key,
        }


@dataclass
class BearToBearishSnapshot:
    generated_ms: int
    scanning: bool
    scanning_label: str
    rows: List[BearToBearishSignal] = field(default_factory=list)
    pcr_history: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    next_scan_ms: int = 0
    auto_scan: bool = True
    market_open: bool = False
    is_paper: bool = True
    auto_execute: bool = False
