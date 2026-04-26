"""
AuthenticatedExchangeAdapter — extends BaseExchangeAdapter with
private account methods that require API credentials.
"""
from abc import abstractmethod
from typing import List, Optional
from app.services.exchanges.base import BaseExchangeAdapter
from app.schemas.account import (
    AssetBalance, AccountPosition, AccountOrder, AccountFill, PortfolioSnapshot
)


class AuthenticatedExchangeAdapter(BaseExchangeAdapter):
    """
    Adapters that support account operations inherit from this class.
    All account methods raise NotImplementedError by default so partial
    implementations still boot cleanly.
    """

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify credentials are valid and API is reachable."""
        ...

    @abstractmethod
    async def get_balances(self) -> List[AssetBalance]:
        ...

    @abstractmethod
    async def get_positions(self) -> List[AccountPosition]:
        ...

    @abstractmethod
    async def get_open_orders(self, underlying: Optional[str] = None) -> List[AccountOrder]:
        ...

    @abstractmethod
    async def get_fills(self, limit: int = 50) -> List[AccountFill]:
        ...

    @abstractmethod
    async def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        ...
