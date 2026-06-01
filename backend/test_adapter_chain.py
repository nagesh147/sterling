import asyncio
from app.services import adapter_manager
from app.services.exchanges import instrument_registry as registry
from app.core.config import settings

async def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Init adapter like main.py
    exchange = settings.exchange_adapter.lower()
    ad = await adapter_manager.init(exchange, "test", "test")
    
    inst = registry.get_instrument("ETH")
    chain = await ad.get_option_chain(inst)
    print("CHAIN LENGTH:", len(chain) if chain else "None")
    
    await adapter_manager.close_current()

asyncio.run(main())
