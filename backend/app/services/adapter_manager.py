"""
Runtime market data adapter manager.
Holds the single shared adapter instance and allows hot-swapping
the underlying exchange without restarting the server.
"""
from typing import Optional
from app.services.exchanges.base import BaseExchangeAdapter
from app.core.logging import get_logger

log = get_logger(__name__)

_adapter: Optional[BaseExchangeAdapter] = None
_data_source: str = "deribit"

SUPPORTED_DATA_SOURCES = {
    "deribit":     "Deribit (BTC/ETH/SOL options + perps)",
    "binance":     "Binance USDT-M Futures (candles/prices)",
    "okx":         "OKX (candles/prices/options)",
    "delta_india": "Delta Exchange India (candles/prices)",
}


def get_adapter() -> Optional[BaseExchangeAdapter]:
    return _adapter


def get_data_source() -> str:
    return _data_source


def _build_raw(exchange: str, api_key: str = "", api_secret: str = "") -> BaseExchangeAdapter:
    exchange = exchange.lower()
    if exchange == "okx":
        from app.services.exchanges.adapters.okx import OKXAdapter
        return OKXAdapter()
    if exchange == "delta_india":
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        return DeltaIndiaAdapter(api_key=api_key, api_secret=api_secret, is_paper=True)
    if exchange == "binance":
        from app.services.exchanges.adapters.binance import BinanceAdapter
        return BinanceAdapter(api_key=api_key, api_secret=api_secret, is_paper=True)
    from app.services.exchanges.adapters.deribit import DeribitAdapter
    from app.core.config import settings
    return DeribitAdapter(base_url=settings.deribit_base_url)


async def init(exchange: str = "deribit", api_key: str = "", api_secret: str = "") -> BaseExchangeAdapter:
    """Build adapter stack and set as active. Called at startup."""
    global _adapter, _data_source
    from app.services.cache import CachingAdapter
    from app.services.retry import RetryingAdapter
    raw = _build_raw(exchange, api_key, api_secret)
    _adapter = CachingAdapter(RetryingAdapter(raw))
    _data_source = exchange.lower()
    log.info("Market data adapter initialized: %s", _data_source)
    return _adapter


async def switch(exchange: str, api_key: str = "", api_secret: str = "") -> BaseExchangeAdapter:
    """Hot-swap the market data adapter at runtime. Closes the old one first."""
    global _adapter
    old = _adapter
    if old is not None:
        try:
            await old.close()
        except Exception as exc:
            log.warning("Error closing old adapter during switch: %s", exc)
    new = await init(exchange, api_key, api_secret)
    log.info("Market data switched to: %s", exchange)
    return new


async def close_current() -> None:
    """Close the current adapter (called at shutdown)."""
    global _adapter
    if _adapter is not None:
        try:
            await _adapter.close()
        except Exception:
            pass
        _adapter = None
