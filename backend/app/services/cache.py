"""
TTL cache wrapper around any BaseExchangeAdapter.
Prevents hammering Deribit on every frontend poll.
"""
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services.exchanges.base import BaseExchangeAdapter
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta

_SENTINEL = object()


class CachingAdapter(BaseExchangeAdapter):
    _TTL: Dict[str, float] = {
        "price":       5.0,
        "perp":        5.0,
        "candles_15m": 15.0,
        "candles_1H":  60.0,
        "candles_4H":  120.0,
        "chain":       30.0,
        "dvol":        60.0,
        "dvol_hist":   3_600.0,
        "ping":        10.0,
    }

    def __init__(self, inner: BaseExchangeAdapter) -> None:
        self._inner = inner
        self._cache: Dict[str, Tuple[float, Any]] = {}

    def _hit(self, key: str, ttl: float) -> Any:
        entry = self._cache.get(key)
        if entry and (time.monotonic() - entry[0]) < ttl:
            return entry[1]
        return _SENTINEL

    def _put(self, key: str, value: Any) -> Any:
        self._cache[key] = (time.monotonic(), value)
        return value

    def invalidate(self, prefix: str = "") -> None:
        if prefix:
            keys = [k for k in self._cache if k.startswith(prefix)]
        else:
            keys = list(self._cache.keys())
        for k in keys:
            del self._cache[k]

    async def ping(self) -> bool:
        hit = self._hit("ping", self._TTL["ping"])
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put("ping", await self._inner.ping())

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        key = f"price:index:{instrument.underlying}"
        hit = self._hit(key, self._TTL["price"])
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put(key, await self._inner.get_index_price(instrument))

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        key = f"price:perp:{instrument.underlying}"
        hit = self._hit(key, self._TTL["perp"])
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put(key, await self._inner.get_perp_price(instrument))

    async def get_candles(
        self,
        instrument: InstrumentMeta,
        resolution: str,
        limit: int = 200,
    ) -> List[Candle]:
        ttl_key = f"candles_{resolution}"
        ttl = self._TTL.get(ttl_key, 60.0)
        key = f"candles:{instrument.underlying}:{resolution}:{limit}"
        hit = self._hit(key, ttl)
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put(key, await self._inner.get_candles(instrument, resolution, limit))

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        key = f"chain:{instrument.underlying}"
        hit = self._hit(key, self._TTL["chain"])
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put(key, await self._inner.get_option_chain(instrument))

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        key = f"dvol:{instrument.underlying}"
        hit = self._hit(key, self._TTL["dvol"])
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put(key, await self._inner.get_dvol(instrument))

    async def get_dvol_history(
        self, instrument: InstrumentMeta, days: int = 30
    ) -> List[float]:
        key = f"dvol_hist:{instrument.underlying}:{days}"
        hit = self._hit(key, self._TTL["dvol_hist"])
        if hit is not _SENTINEL:
            return hit  # type: ignore[return-value]
        return self._put(key, await self._inner.get_dvol_history(instrument, days))

    async def close(self) -> None:
        if hasattr(self._inner, "close"):
            await self._inner.close()  # type: ignore[attr-defined]
