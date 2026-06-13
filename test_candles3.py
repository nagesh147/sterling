import asyncio
import httpx
import urllib.parse

async def main():
    sym = "NSE:NIFTY 50"
    url = f"http://localhost:8000/api/v1/candles/{urllib.parse.quote(sym)}?tf=5m&limit=10"
    print(url)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url)
        print(r.status_code)
        print(r.text[:500])

asyncio.run(main())
