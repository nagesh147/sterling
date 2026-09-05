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
_data_source: str = "zerodha"
_raw_adapter: Optional[BaseExchangeAdapter] = None   # unwrapped, for WS access

SUPPORTED_DATA_SOURCES = {
    "zerodha": "Zerodha/Kite Connect (Indian equities/options)",
}


def get_adapter() -> Optional[BaseExchangeAdapter]:
    return _adapter


def get_raw_adapter() -> Optional[BaseExchangeAdapter]:
    """Return the unwrapped adapter (no cache/retry). Used for direct WS price access."""
    return _raw_adapter


def get_data_source() -> str:
    return _data_source


def _build_raw(exchange: str, api_key: str = "", api_secret: str = "") -> BaseExchangeAdapter:
    exchange = exchange.lower()
    if exchange == "zerodha":
        from app.services.exchanges.adapters.zerodha import ZerodhaAdapter
        return ZerodhaAdapter(api_key=api_key, api_secret=api_secret, access_token="", is_paper=True)
    raise ValueError(f"Unsupported exchange: {exchange}. Supported: zerodha")


async def init(
    exchange: str = "zerodha",
    api_key: str = "",
    api_secret: str = "",
    start_ws: bool = True,
) -> BaseExchangeAdapter:
    """Build adapter stack and set as active. Called at startup."""
    global _adapter, _data_source, _raw_adapter
    from app.services.cache import CachingAdapter
    from app.services.retry import RetryingAdapter
    # A legacy crypto account row left in the database (delta_india, okx, ...)
    # must not take the whole API down on an Indian-only build. `_build_raw`
    # raises for anything but zerodha, and startup called it with whatever the
    # persisted active account said — so one stale row meant
    # "Application startup failed. Exiting." and no backend at all.
    try:
        raw = _build_raw(exchange, api_key, api_secret)
    except ValueError:
        log.warning(
            "Ignoring unsupported persisted exchange %r; falling back to zerodha.",
            exchange,
        )
        exchange = "zerodha"
        raw = _build_raw(exchange, api_key, api_secret)

    _adapter = CachingAdapter(RetryingAdapter(raw))
    _data_source = exchange.lower()
    _raw_adapter = raw

    log.info("Market data adapter initialized: %s", _data_source)
    return _adapter


async def start_feed() -> None:
    """Start WebSocket price feed if active raw adapter supports it."""
    log.info("Start feed called for %s (no-op for zerodha)", _data_source)


async def stop_feed() -> None:
    """Stop WebSocket price feed if active raw adapter supports it."""
    log.info("Stop feed called for %s (no-op for zerodha)", _data_source)


async def switch(
    exchange: str,
    api_key: str = "",
    api_secret: str = "",
    start_ws: bool = True,
) -> BaseExchangeAdapter:
    """Hot-swap the market data adapter at runtime. Closes the old one first."""
    global _adapter
    old = _adapter
    if old is not None:
        try:
            await old.close()
        except Exception as exc:
            log.warning("Error closing old adapter during switch: %s", exc)
    new = await init(exchange, api_key, api_secret, start_ws=start_ws)
    log.info("Market data switched to: %s", exchange)
    return new


async def close_current() -> None:
    """Close the current adapter (called at shutdown)."""
    global _adapter
    if _adapter is not None:
        try:
            await _adapter.close()
        except Exception as _exc:
            log.debug("suppressed: %s", _exc)
        _adapter = None


# Backward-compatible aliases
start_ws_feed = start_feed
stop_ws_feed = stop_feed

