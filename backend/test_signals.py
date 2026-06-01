import asyncio
from fastapi import Request
from main import app
from app.api.v1.endpoints.derivatives import _collect_armed_signals

class MockRequest:
    def __init__(self, app):
        self.app = app

async def main():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    app.state.algo_mode = True
    req = MockRequest(app)
    
    print("Collecting armed signals directly...")
    try:
        # We need to not swallow exceptions from scalping
        signals = _collect_armed_signals(req, strategy_filter=None, underlying_filter=None)
        print(f"Collected {len(signals)} signals:")
        for sid, sig in signals:
            print(f"- {sid} -> {sig}")
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
