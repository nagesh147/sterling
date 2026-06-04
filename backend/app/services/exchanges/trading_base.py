"""
TradingExchangeAdapter — the enforced order-placement contract.

Lifts the methods that today live only on the concrete DeltaIndiaAdapter (and
the informal _AsyncAdapterShim inside order_router.py) into an abstract base so
EVERY order-capable broker has a checked surface. Signatures mirror what Delta
already implements — this is a formalization, not a behavior change.

Optional capability methods (set_leverage, set_margin_mode, cancel_replace_stop,
market_reduce_close) default to NotImplementedError so a partial adapter still
boots; OrderRouter feature-detects / guards each call (see order_router.py).
"""
from abc import abstractmethod
from typing import Optional

from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter


class TradingExchangeAdapter(AuthenticatedExchangeAdapter):
    # ── required order surface ────────────────────────────────────────────
    @abstractmethod
    async def get_product_id(self, symbol: str) -> int:
        ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market_order",
        limit_price: Optional[float] = None,
        time_in_force: str = "gtc",
        post_only: bool = False,
        reduce_only: bool = False,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trail_amount: Optional[float] = None,
        **kwargs,
    ) -> dict:
        ...

    @abstractmethod
    async def place_order_option(
        self,
        option_symbol: str,
        side: str,
        size: float,
        order_type: str = "market_order",
        limit_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> dict:
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, product_id: int) -> dict:
        ...

    # ── optional capabilities (override where supported) ──────────────────
    async def set_leverage(self, product_id: int, leverage: float) -> None:
        raise NotImplementedError("set_leverage not supported by this adapter")

    async def set_margin_mode(self, product_id: int, mode: str) -> None:
        raise NotImplementedError("set_margin_mode not supported by this adapter")

    async def cancel_replace_stop(self, **kwargs) -> dict:
        raise NotImplementedError("cancel_replace_stop not supported by this adapter")

    async def market_reduce_close(self, **kwargs) -> dict:
        raise NotImplementedError("market_reduce_close not supported by this adapter")
