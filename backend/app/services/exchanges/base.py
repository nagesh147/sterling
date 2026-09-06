from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta


class BaseExchangeAdapter(ABC):
    """Abstract exchange adapter. All public-data methods; no auth required."""

    @abstractmethod
    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        ...

    @abstractmethod
    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        ...

    @abstractmethod
    async def get_candles(
        self,
        instrument: InstrumentMeta,
        resolution: str,
        limit: int = 200,
    ) -> List[Candle]:
        """resolution: '15m' | '1H' | '4H'"""
        ...

    @abstractmethod
    async def get_option_chain(
        self, instrument: InstrumentMeta
    ) -> List[OptionSummary]:
        ...

    @abstractmethod
    async def ping(self) -> bool:
        ...
