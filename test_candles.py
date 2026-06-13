import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://localhost:8000/api/v1/candles/NSE:NIFTY%2050?tf=5m&limit=10")
        print(r.status_code, r.text)

asyncio.run(main())
