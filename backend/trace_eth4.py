import asyncio
from app.api.v1.endpoints.derivatives import _option_chain_or_none
import urllib.request
import json
from fastapi import Request

class DummyApp:
    state = type("State", (), {})()
    
async def trace():
    app = DummyApp()
    import app.services.exchanges.adapters.delta_india as da
    import aiohttp
    session = aiohttp.ClientSession()
    app.state.adapter = da.DeltaIndiaAdapter(session)
    chain = await _option_chain_or_none(underlying="ETH", app=app, spot=2000)
    print("Chain size:", len(chain) if chain is not None else "None")
    await session.close()
        
asyncio.run(trace())
