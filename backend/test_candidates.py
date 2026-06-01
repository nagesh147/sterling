import asyncio
from app.services import adapter_manager
from app.services.exchanges import instrument_registry as registry
from app.core.config import settings
from app.engines.derivatives.schemas import StrategyDerivativesProfile, SignalContext, MarketContext
from app.engines.derivatives.selector import _build_options_candidates
from app.api.v1.endpoints.derivatives import enrich_chain

async def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    
    exchange = settings.exchange_adapter.lower()
    ad = await adapter_manager.init(exchange, "test", "test")
    
    inst = registry.get_instrument("ETH")
    chain = await ad.get_option_chain(inst)
    enriched = enrich_chain(chain, spot=3500.0)
    
    # Mock profile and signal
    profile = StrategyDerivativesProfile(
        strategy="scalping/delta_gamma",
        enabled=True,
        instrument_bias="options",
        expected_hold_minutes=120,
    )
    signal = SignalContext(
        strategy="scalping/delta_gamma",
        underlying="ETH",
        direction="long",
        entry=3500.0,
        stop_loss=3400.0,
        take_profit=3800.0,
        signal_score=60.0,
        expected_hold_minutes=120,
    )
    market = MarketContext(
        underlying="ETH",
        spot=3500.0,
    )
    
    candidates = _build_options_candidates(
        signal=signal, market=market, profile=profile, chain=enriched
    )
    print("OPTIONS CANDIDATES:", len(candidates))
    
    await adapter_manager.close_current()

asyncio.run(main())
