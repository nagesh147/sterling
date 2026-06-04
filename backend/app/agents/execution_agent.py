"""ExecutionAgent — wraps the existing OrderRouter, announcing order lifecycle.

Delegates routing/safety entirely to OrderRouter.submit (paper/shadow/live);
this agent only translates the call into bus events so PNL/Reconciliation
agents can react. No safety logic is duplicated here.
"""
from __future__ import annotations

from typing import Any, Optional

from app.bus.event_bus import EventBus
from app.domain.events import OrderSubmitted, OrderAccepted, OrderRejected


class ExecutionAgent:
    def __init__(self, router: Any, bus: Optional[EventBus] = None) -> None:
        self.router = router
        self.bus = bus

    async def execute(self, req: Any) -> Any:
        if self.bus is not None:
            await self.bus.publish(OrderSubmitted(payload={
                "underlying": getattr(req, "underlying", ""),
                "direction": getattr(req, "direction", ""),
                "instrument_type": getattr(req, "instrument_type", ""),
            }))
        resp = await self.router.submit(req)
        if self.bus is not None:
            if getattr(resp, "accepted", False):
                await self.bus.publish(OrderAccepted(order_id=getattr(resp, "order_id", "") or ""))
            else:
                await self.bus.publish(OrderRejected(code=getattr(resp, "code", "") or ""))
        return resp
