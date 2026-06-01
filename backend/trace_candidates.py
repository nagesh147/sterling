import asyncio
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals
from app.engines.derivatives.selector import decide_both
from fastapi import Request

class DummyApp:
    state = type('State', (), {})()
    
class DummyRequest:
    app = DummyApp()

async def trace():
    req = DummyRequest()
    try:
        signals = _collect_armed_signals(req, strategy_filter=None, underlying_filter=None)
        print("Armed signals:", len(signals))
        for signal_id, sig in signals:
            print(f"- {signal_id}: {sig.strategy}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(trace())
