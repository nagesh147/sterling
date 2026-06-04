"""BrokerAgent — thin facade over an exchange adapter (auth/order surface).

Delegates to the injected adapter (a TradingExchangeAdapter / BrokerProtocol);
optionally announces order outcomes on the bus. Moves no logic.
"""
from __future__ import annotations

from typing import Any, Optional

from app.bus.event_bus import EventBus
from app.domain.events import OrderAccepted


class BrokerAgent:
    def __init__(self, adapter: Any, bus: Optional[EventBus] = None) -> None:
        self.adapter = adapter
        self.bus = bus

    async def place_order(self, **kwargs) -> dict:
        result = await self.adapter.place_order(**kwargs)
        if self.bus is not None:
            await self.bus.publish(OrderAccepted(order_id=str((result or {}).get("id", ""))))
        return result

    async def cancel_order(self, order_id: str, product_id: int) -> dict:
        return await self.adapter.cancel_order(order_id, product_id)
