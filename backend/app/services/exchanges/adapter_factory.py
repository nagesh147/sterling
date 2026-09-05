"""
Creates authenticated adapter instances from exchange configs.
"""
from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter


def create_account_adapter(cfg: ExchangeConfig) -> AuthenticatedExchangeAdapter:
    """Return the right adapter for the given exchange config."""
    name = cfg.name.lower()

    if name == "zerodha":
        from app.services.exchanges.adapters.zerodha import ZerodhaAdapter
        access_token = cfg.extra.get("access_token", "")
        return ZerodhaAdapter(
            api_key=cfg.api_key,
            api_secret=cfg.api_secret,
            access_token=access_token,
            is_paper=cfg.is_paper,
        )

    raise ValueError(
        f"No account adapter for exchange: {cfg.name!r}. "
        f"Supported: zerodha"
    )
