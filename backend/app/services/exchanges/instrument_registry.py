from typing import Dict, Optional, List
from app.schemas.instruments import InstrumentMeta

_REGISTRY: Dict[str, InstrumentMeta] = {
    "NIFTY": InstrumentMeta(
        underlying="NIFTY",
        quote_currency="INR",
        contract_multiplier=50.0,
        tick_size=0.05,
        strike_step=50.0,
        min_dte=1,
        preferred_dte_min=7,
        preferred_dte_max=21,
        force_exit_dte=1,
        has_options=True,
        exchange="zerodha",
        exchange_currency="INR",
        index_name="NIFTY 50",
        zerodha_token=256265,
        zerodha_index_symbol="NSE:NIFTY 50",
        zerodha_vix_token=264969,
        description="NIFTY 50 Index Options (NSE via Zerodha Kite)",
    ),
    "BANKNIFTY": InstrumentMeta(
        underlying="BANKNIFTY",
        quote_currency="INR",
        contract_multiplier=25.0,
        tick_size=0.05,
        strike_step=100.0,
        min_dte=1,
        preferred_dte_min=7,
        preferred_dte_max=21,
        force_exit_dte=1,
        has_options=True,
        exchange="zerodha",
        exchange_currency="INR",
        index_name="NIFTY Bank",
        zerodha_token=260105,
        zerodha_index_symbol="NSE:NIFTY BANK",
        zerodha_vix_token=264969,
        description="Bank Nifty Index Options (NSE via Zerodha Kite)",
    ),
}


def get_instrument(underlying: str) -> Optional[InstrumentMeta]:
    return _REGISTRY.get(underlying.upper())


def list_instruments() -> List[InstrumentMeta]:
    return list(_REGISTRY.values())


def is_supported(underlying: str) -> bool:
    return underlying.upper() in _REGISTRY


def has_options(underlying: str) -> bool:
    inst = get_instrument(underlying)
    return inst.has_options if inst else False
