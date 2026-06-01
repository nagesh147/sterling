import asyncio
from main import app
from app.api.v1.endpoints.scalping import get_config, set_config
from app.engines.scalping.config import default_config

class MockRequest:
    def __init__(self, app):
        self.app = app

async def main():
    req = MockRequest(app)
    # 1. Get default config
    cfg = default_config()
    cfg.use_optimized = True # turn ON gatekeeper
    
    # 2. Try to set it
    print("Calling set_config...")
    try:
        resp = await set_config(cfg, req)
        print("Success! Response use_optimized:", resp.config.use_optimized)
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
