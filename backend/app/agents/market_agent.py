"""MarketAgent — thin facade normalizing market-data access via an adapter."""
from __future__ import annotations

from typing import Any, List


class MarketAgent:
    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    async def price(self, instrument: Any) -> float:
        return await self.adapter.get_index_price(instrument)

    async def candles(self, instrument: Any, resolution: str, limit: int = 200) -> List[Any]:
        return await self.adapter.get_candles(instrument, resolution, limit)
