"""
TradeEvent taxonomy (Phase 3) — the concrete events that flow over the bus.

Each subclass fixes its `event_type` and may add typed fields. They remain
pure domain objects (pydantic models); the bus and agents live in app/bus and
app/agents respectively.
"""
from __future__ import annotations

from app.domain.models import TradeEvent


class SignalRaised(TradeEvent):
    event_type: str = "SignalRaised"


class OrderSubmitted(TradeEvent):
    event_type: str = "OrderSubmitted"


class OrderAccepted(TradeEvent):
    event_type: str = "OrderAccepted"
    order_id: str = ""


class OrderRejected(TradeEvent):
    event_type: str = "OrderRejected"
    code: str = ""


class FillReceived(TradeEvent):
    event_type: str = "FillReceived"
    symbol: str = ""
    side: str = ""
    size: float = 0.0
    price: float = 0.0


class PositionClosed(TradeEvent):
    event_type: str = "PositionClosed"
    symbol: str = ""
    realized_pnl_usd: float = 0.0


class RiskBreach(TradeEvent):
    event_type: str = "RiskBreach"


class Heartbeat(TradeEvent):
    event_type: str = "Heartbeat"
