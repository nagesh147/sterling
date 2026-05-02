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
        delta_perp_symbol="BTCUSDT",
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
        delta_perp_symbol="ETHUSDT",
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
        perp_symbol="",
        index_name="NIFTY 50",
        dvol_symbol=None,
        zerodha_token=256265,
        zerodha_index_symbol="NSE:NIFTY 50",
        zerodha_vix_token=264969,
        description="NIFTY 50 Index Options (NSE via Zerodha Kite — Zerodha adapter only)",
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
        perp_symbol="",
        index_name="NIFTY Bank",
        dvol_symbol=None,
        zerodha_token=260105,
        zerodha_index_symbol="NSE:NIFTY BANK",
        zerodha_vix_token=264969,
        description="Bank Nifty Index Options (NSE via Zerodha Kite — Zerodha adapter only)",
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
