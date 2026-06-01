import asyncio
from app.services import adapter_manager
from app.services.exchanges import instrument_registry as registry
from app.core.config import settings
from app.engines.derivatives.schemas import StrategyDerivativesProfile, SignalContext, MarketContext
from app.api.v1.endpoints.derivatives import _market_context, _option_chain_or_none
from app.engines.derivatives.preview import preview_one
from fastapi import FastAPI
import pprint

async def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    
    app = FastAPI()
    
    exchange = settings.exchange_adapter.lower()
    ad = await adapter_manager.init(exchange, "test", "test")
    app.state.adapter = ad
    
    sig = SignalContext(
        strategy="scalping/delta_gamma",
        underlying="ETH",
        direction="long",
        entry=3500.0,
        stop_loss=3400.0,
        take_profit=3800.0,
        atr=100.0,
        signal_score=60.0,
    )
    
    market = await _market_context(underlying="ETH", app=app, signal_score=60.0)
    chain = await _option_chain_or_none(underlying="ETH", app=app, spot=market.spot)
    
    overrides = {
        "scalping/delta_gamma": StrategyDerivativesProfile(
            strategy="scalping/delta_gamma",
            enabled=True,
            instrument_bias="options",
            dte_preferred=1,
            dte_max=7,
            expected_hold_minutes=75,
        )
    }
    
    decision = preview_one(
        signal=sig, market=market, chain=chain, profile_overrides=overrides
    )
    pprint.pprint(decision.model_dump())
    
    await adapter_manager.close_current()

asyncio.run(main())
