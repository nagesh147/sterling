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
_data_source: str = "delta_india"
_raw_adapter: Optional[BaseExchangeAdapter] = None   # unwrapped, for WS access

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


async def init(exchange: str = "delta_india", api_key: str = "", api_secret: str = "") -> BaseExchangeAdapter:
    """Build adapter stack and set as active. Called at startup."""
    global _adapter, _data_source, _raw_adapter
    from app.services.cache import CachingAdapter
    from app.services.retry import RetryingAdapter
    raw = _build_raw(exchange, api_key, api_secret)
    _adapter = CachingAdapter(RetryingAdapter(raw))
    _data_source = exchange.lower()
    _raw_adapter = raw

    # Start WebSocket live price feed for delta_india (eliminates REST ticker polling)
    if _data_source == "delta_india" and hasattr(raw, "start_ws"):
        from app.services.exchanges.instrument_registry import list_instruments
        symbols = [i.delta_perp_symbol for i in list_instruments() if i.delta_perp_symbol]
        await raw.start_ws(symbols)

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
