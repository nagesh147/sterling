"""Canonical domain models: new primitives + re-exports of existing schemas."""
from __future__ import annotations

import time
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

# ── Re-export existing canonical schemas (single import surface) ──────────
from app.schemas.market import Candle, OptionSummary  # noqa: F401
from app.schemas.instruments import InstrumentMeta  # noqa: F401
from app.schemas.account import (  # noqa: F401
    AssetBalance, AccountPosition, AccountOrder, AccountFill, PortfolioSnapshot,
)
from app.schemas.risk import RiskParams  # noqa: F401


# ── New primitives ────────────────────────────────────────────────────────
class Signal(BaseModel):
    """Normalized strategy output — independent of broker and market.

    Mirrors the signal-relevant fields the OrderRouter already consumes via
    OrderRouterRequest, so strategies stay broker/market-agnostic.
    """
    underlying: str
    direction: Literal["long", "short"]
    instrument_type: Literal["futures", "options"] = "futures"
    score: float = 0.0
    strength: str = "SIGNAL"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    size_hint: float = 1.0
    option_symbol: Optional[str] = None
    source: str = ""
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class TradeEvent(BaseModel):
    """Base event for the in-process bus (taxonomy extended in Phase 3)."""
    event_type: str
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    payload: Dict[str, Any] = Field(default_factory=dict)
