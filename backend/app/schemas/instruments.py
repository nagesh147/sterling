from pydantic import BaseModel, Field, computed_field
from typing import Optional, Tuple, List


class InstrumentMeta(BaseModel):
    underlying: str
    quote_currency: str = "INR"
    contract_multiplier: float = 1.0
    tick_size: float
    strike_step: float
    min_dte: int = 5
    preferred_dte_min: int = 10
    preferred_dte_max: int = 15
    force_exit_dte: int = 3
    has_options: bool = True
    exchange: str = "zerodha"
    exchange_currency: str
    index_name: str
    description: str = ""
    # Zerodha Kite-specific
    zerodha_token: Optional[int] = None            # instrument token for historical data
    zerodha_index_symbol: Optional[str] = None     # e.g. "NSE:NIFTY 50" for LTP/quote
    zerodha_vix_token: Optional[int] = None        # India VIX instrument token (264969)

    @computed_field
    @property
    def compatible_sources(self) -> List[str]:
        """Data sources that can provide market data for this instrument."""
        # Zerodha is the only market-data adapter this build can construct.
        return ["zerodha"] if self.exchange == "zerodha" else []


class InstrumentListResponse(BaseModel):
    instruments: List[InstrumentMeta]
    count: int


class InstrumentDetailResponse(BaseModel):
    instrument: InstrumentMeta
    supported: bool
    options_available: bool
