"""RiskAgent — evaluates injected risk rules; first breach wins (fail-closed).

Each rule is a callable(context) -> Optional[str] (None = allow, str = breach
code), matching RiskRuleProtocol. The separated RiskEngine (Phase 4) will
provide the rule set; here the agent simply orchestrates evaluation + emits
RiskBreach. Rules may be sync or async.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable, List, Optional

from app.bus.event_bus import EventBus
from app.domain.events import RiskBreach


class RiskAgent:
    def __init__(self, rules: Optional[List[Callable[[Any], Optional[str]]]] = None,
                 bus: Optional[EventBus] = None) -> None:
        self.rules = rules or []
        self.bus = bus

    async def check(self, context: Any) -> Optional[str]:
        for rule in self.rules:
            result = rule(context)
            if inspect.isawaitable(result):
                result = await result
            if result:
                if self.bus is not None:
                    await self.bus.publish(RiskBreach(payload={"code": result}))
                return result
        return None
