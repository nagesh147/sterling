import asyncio
import httpx
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter

async def main():
    adapter = DeltaIndiaAdapter(api_key="", api_secret="")
    ticker = await adapter.get_ticker("ETHUSD")
    spot = ticker.mark_price
    print(f"Current ETH spot: {spot}")
    
    url = f"http://localhost:8000/api/v1/derivatives/preview?underlying=ETH&strategy=scalping/delta_gamma&direction=long&entry={spot}&stop_loss={spot*0.99}&take_profit={spot*1.02}&expected_hold_minutes=75"
    print(f"URL: {url}")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        print("Response:", resp.json())

asyncio.run(main())
