"""PNLAgent — subscribes to fills & closes, tracks running P&L.

The reference subscriber for the bus: on construction with a bus it wires
itself to FillReceived and PositionClosed. Delegates nowhere — it only
aggregates. (The authoritative P&L store remains paper_store; this is the
event-driven mirror the spec's reference flow demonstrates.)
"""
from __future__ import annotations

from typing import List, Optional

from app.bus.event_bus import EventBus
from app.domain.events import FillReceived, PositionClosed


class PNLAgent:
    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self.fills: List[FillReceived] = []
        self.realized_pnl_usd: float = 0.0
        if bus is not None:
            bus.subscribe(FillReceived, self.on_fill)
            bus.subscribe(PositionClosed, self.on_position_closed)

    def on_fill(self, event: FillReceived) -> None:
        self.fills.append(event)

    def on_position_closed(self, event: PositionClosed) -> None:
        self.realized_pnl_usd += event.realized_pnl_usd

    def snapshot(self) -> dict:
        return {"fills": len(self.fills), "realized_pnl_usd": self.realized_pnl_usd}
