"""Structural interfaces (Protocols) for the plug-and-play boundaries.

Runtime-checkable so contract tests can assert an adapter/strategy conforms
without importing concrete types. These describe the SAME surface the existing
ABCs enforce; Protocols add structural checks usable across layers.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from app.domain.models import Signal


@runtime_checkable
class BrokerProtocol(Protocol):
    async def get_product_id(self, symbol: str) -> int: ...
    async def place_order(self, symbol: str, side: str, size: float, **kwargs) -> dict: ...
    async def cancel_order(self, order_id: str, product_id: int) -> dict: ...


@runtime_checkable
class MarketAdapterProtocol(Protocol):
    async def get_index_price(self, instrument) -> float: ...
    async def get_candles(self, instrument, resolution: str, limit: int = 200): ...


@runtime_checkable
class StrategyProtocol(Protocol):
    def generate(self, *args, **kwargs) -> List[Signal]: ...


@runtime_checkable
class RiskRuleProtocol(Protocol):
    def evaluate(self, context) -> Optional[str]:
        """Return None to allow, or a machine-readable breach code to reject."""
        ...
