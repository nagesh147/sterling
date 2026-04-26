from typing import Dict, Optional, List
from app.schemas.instruments import InstrumentMeta

_REGISTRY: Dict[str, InstrumentMeta] = {
    "BTC": InstrumentMeta(
        underlying="BTC",
        quote_currency="USD",
        contract_multiplier=1.0,
        tick_size=0.5,
        strike_step=1000.0,
        has_options=True,
        exchange="deribit",
        exchange_currency="BTC",
        perp_symbol="BTC-PERPETUAL",
        index_name="btc_usd",
        dvol_symbol="BTC-DVOL",
        okx_perp_symbol="BTC-USDT-SWAP",
        okx_index_id="BTC-USDT",
        okx_underlying="BTC-USD",
        delta_perp_symbol="BTCUSD",
        delta_option_underlying="BTC",
        description="Bitcoin",
    ),
    "ETH": InstrumentMeta(
        underlying="ETH",
        quote_currency="USD",
        contract_multiplier=1.0,
        tick_size=0.05,
        strike_step=100.0,
        has_options=True,
        exchange="deribit",
        exchange_currency="ETH",
        perp_symbol="ETH-PERPETUAL",
        index_name="eth_usd",
        dvol_symbol="ETH-DVOL",
        okx_perp_symbol="ETH-USDT-SWAP",
        okx_index_id="ETH-USDT",
        okx_underlying="ETH-USD",
        delta_perp_symbol="ETHUSD",
        delta_option_underlying="ETH",
        description="Ethereum",
    ),
    "SOL": InstrumentMeta(
        underlying="SOL",
        quote_currency="USD",
        contract_multiplier=1.0,
        tick_size=0.001,
        strike_step=5.0,
        has_options=True,
        exchange="deribit",
        exchange_currency="SOL",
        perp_symbol="SOL-PERPETUAL",
        index_name="sol_usd",
        dvol_symbol=None,
        okx_perp_symbol="SOL-USDT-SWAP",
        okx_index_id="SOL-USDT",
        okx_underlying=None,
        delta_perp_symbol="SOLUSDT",
        delta_option_underlying=None,
        description="Solana",
    ),
    "XRP": InstrumentMeta(
        underlying="XRP",
        quote_currency="USD",
        contract_multiplier=1.0,
        tick_size=0.0001,
        strike_step=0.05,
        has_options=False,
        exchange="deribit",
        exchange_currency="XRP",
        perp_symbol="XRP-PERPETUAL",
        index_name="xrp_usd",
        dvol_symbol=None,
        okx_perp_symbol="XRP-USDT-SWAP",
        okx_index_id="XRP-USDT",
        okx_underlying=None,
        delta_perp_symbol="XRPUSDT",
        delta_option_underlying=None,
        description="XRP – no options on Deribit",
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
