"""
Creates authenticated adapter instances from exchange configs.
"""
from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter


def create_account_adapter(cfg: ExchangeConfig) -> AuthenticatedExchangeAdapter:
    """Return the right adapter for the given exchange config."""
    name = cfg.name.lower()

    if name == "delta_india":
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        return DeltaIndiaAdapter(
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            is_paper=cfg.is_paper,
        )

    if name == "zerodha":
        from app.services.exchanges.adapters.zerodha import ZerodhaAdapter
        access_token = cfg.extra.get("access_token", "")
        return ZerodhaAdapter(
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            access_token=access_token,
            is_paper=cfg.is_paper,
        )

    if name == "binance":
        from app.services.exchanges.adapters.binance import BinanceAdapter
        return BinanceAdapter(
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            is_paper=cfg.is_paper,
        )

    if name == "deribit":
        from app.services.exchanges.adapters.deribit import DeribitAdapter
        return DeribitAdapter()

    if name == "okx":
        from app.services.exchanges.adapters.okx import OKXAdapter
        return OKXAdapter()

    raise ValueError(
        f"No account adapter for exchange: {cfg.name!r}. "
        f"Supported: delta_india, zerodha, deribit, okx"
    )
