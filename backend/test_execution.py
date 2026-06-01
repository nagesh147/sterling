import asyncio
from main import app
from app.services.derivatives_scanner import run_scanner_tick

async def main():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock algo mode to ON
    app.state.algo_mode = True
    
    # Run a tick
    print("Running scanner tick...")
    cache = await run_scanner_tick(app)
    print("Scanner cache:")
    print(cache)

if __name__ == "__main__":
    asyncio.run(main())
