import asyncio
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals, _profile_overrides
from app.engines.derivatives.profiles import StrategyDerivativesProfile
import urllib.request
import json

class DummyApp:
    state = type('State', (), {})()

class DummyRequest:
    app = DummyApp()

async def trace():
    req = urllib.request.Request("http://localhost:8000/api/v1/derivatives/config")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
    
    overrides = {}
    for k, v in data["profiles"].items():
        overrides[k] = StrategyDerivativesProfile(**v)
        
    req_proxy = DummyRequest()
    req_proxy.app.state.derivatives_profile_overrides = overrides
    
    futures_rows, options_rows, ts = await _both_rows(
        req_proxy, strategy_filter=None, underlying_filter=None
    )
    print(f"Futures rows: {len(futures_rows)}")
    print(f"Options rows: {len(options_rows)}")

asyncio.run(trace())
