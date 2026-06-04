"""
event_emit — optional live emission of TradeEvents from sync code paths.

The bus is None until configure() is called at startup (only when
settings.enable_event_bus is true). So by default every emit_* is a cheap
no-op and the running app is unchanged. All emits are fail-safe.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

_bus: Optional[Any] = None
_agents: Dict[str, Any] = {}


def configure(bus: Any, agents: Optional[Dict[str, Any]] = None) -> None:
    global _bus, _agents
    _bus = bus
    _agents = agents or {}


def reset() -> None:
    global _bus, _agents
    _bus = None
    _agents = {}


def is_enabled() -> bool:
    return _bus is not None


def agent(name: str) -> Optional[Any]:
    return _agents.get(name)


def emit_position_closed(symbol: str, realized_pnl_usd: float) -> None:
    if _bus is None:
        return
    try:
        from app.domain.events import PositionClosed
        _bus.publish_sync(PositionClosed(symbol=symbol, realized_pnl_usd=float(realized_pnl_usd)))
    except Exception as exc:
        log.warning("emit_position_closed failed (non-fatal): %s", exc)


def emit_fill(symbol: str, side: str, size: float, price: float) -> None:
    if _bus is None:
        return
    try:
        from app.domain.events import FillReceived
        _bus.publish_sync(FillReceived(symbol=symbol, side=side, size=float(size), price=float(price)))
    except Exception as exc:
        log.warning("emit_fill failed (non-fatal): %s", exc)
