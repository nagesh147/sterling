"""
Retry adapter — wraps any BaseExchangeAdapter with exponential-backoff retry
and per-call asyncio timeout.

Stack in production: CachingAdapter(RetryingAdapter(DeribitAdapter())).
"""
import asyncio
from typing import Callable, List, Optional

from app.services.exchanges.base import BaseExchangeAdapter
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta
from app.core.logging import get_logger

log = get_logger(__name__)


class RetryingAdapter(BaseExchangeAdapter):
    def __init__(
        self,
        inner: BaseExchangeAdapter,
        max_attempts: int = 3,
        base_delay: float = 0.4,
        call_timeout: float = 8.0,
    ) -> None:
        self._inner = inner
        self._max = max_attempts
        self._delay = base_delay
        self._timeout = call_timeout

    async def _retry(self, fn: Callable):
        """Call fn() with timeout, retry on exception with exponential backoff."""
        last_exc: Exception = RuntimeError("no attempts")
        for attempt in range(self._max):
            try:
                return await asyncio.wait_for(fn(), timeout=self._timeout)
            except (asyncio.TimeoutError, Exception) as exc:
                last_exc = exc
                if attempt < self._max - 1:
                    wait = self._delay * (2 ** attempt)
                    log.warning(
                        "Attempt %d/%d failed (%.1fs timeout, err: %s). Retry in %.2fs.",
                        attempt + 1, self._max, self._timeout, exc, wait,
                    )
                    await asyncio.sleep(wait)
        raise last_exc

    async def ping(self) -> bool:
        try:
            return await self._retry(lambda: self._inner.ping())
        except Exception:
            return False

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        return await self._retry(lambda: self._inner.get_index_price(instrument))

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self._retry(lambda: self._inner.get_spot_price(instrument))

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        return await self._retry(lambda: self._inner.get_perp_price(instrument))

    async def get_candles(
        self, instrument: InstrumentMeta, resolution: str, limit: int = 200
    ) -> List[Candle]:
        return await self._retry(
            lambda: self._inner.get_candles(instrument, resolution, limit)
        )

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        return await self._retry(lambda: self._inner.get_option_chain(instrument))

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        try:
            return await self._retry(lambda: self._inner.get_dvol(instrument))
        except Exception:
            return None

    async def get_dvol_history(
        self, instrument: InstrumentMeta, days: int = 30
    ) -> List[float]:
        try:
            return await self._retry(
                lambda: self._inner.get_dvol_history(instrument, days)
            )
        except Exception:
            return []

    async def close(self) -> None:
        if hasattr(self._inner, "close"):
            await self._inner.close()  # type: ignore[attr-defined]
