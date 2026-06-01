import asyncio
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals, _profile_overrides
from app.engines.derivatives.selector import decide_both
from app.engines.derivatives.profiles import get_profile
from fastapi import Request

class DummyApp:
    state = type('State', (), {})()

class DummyRequest:
    app = DummyApp()

async def trace():
    req = DummyRequest()
    signals = _collect_armed_signals(req, strategy_filter=None, underlying_filter=None)
    overrides = _profile_overrides(req.app)
    
    for signal_id, sig in signals:
        prof = overrides.get(sig.strategy) or get_profile(sig.strategy)
        print(f"{sig.strategy}: enabled={prof.enabled}")

asyncio.run(trace())
