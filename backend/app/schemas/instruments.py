from pydantic import BaseModel, Field, computed_field
from typing import Optional, Tuple, List


class InstrumentMeta(BaseModel):
    underlying: str
    quote_currency: str = "USD"
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
    perp_symbol: str
    index_name: str
    dvol_symbol: Optional[str] = None
    description: str = ""
    # OKX-specific
    okx_perp_symbol: Optional[str] = None
    okx_index_id: Optional[str] = None
    okx_underlying: Optional[str] = None

    # Delta Exchange India-specific
    delta_perp_symbol: Optional[str] = None        # e.g. "BTCUSD" or "BTCUSDT"
    delta_option_underlying: Optional[str] = None  # e.g. "BTC" for option chain
    # Zerodha Kite-specific
    zerodha_token: Optional[int] = None            # instrument token for historical data
    zerodha_index_symbol: Optional[str] = None     # e.g. "NSE:NIFTY 50" for LTP/quote
    zerodha_vix_token: Optional[int] = None        # India VIX token (264969) for DVOL proxy

    @computed_field
    @property
    def compatible_sources(self) -> List[str]:
        """Data sources that can provide market data for this instrument."""
        # Zerodha is the only adapter this build can construct. The crypto
        # branches below used to append deribit/binance unconditionally, so a
        # non-zerodha instrument advertised sources that cannot be built.
        return ["zerodha"] if self.exchange == "zerodha" else []


class InstrumentListResponse(BaseModel):
    instruments: List[InstrumentMeta]
    count: int


class InstrumentDetailResponse(BaseModel):
    instrument: InstrumentMeta
    supported: bool
    options_available: bool
    perp_symbol: str
