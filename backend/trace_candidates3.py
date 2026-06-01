import asyncio
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals, _profile_overrides
from app.engines.derivatives.selector import decide_both
from app.engines.derivatives.schemas import MarketContext
from app.engines.derivatives.profiles import StrategyDerivativesProfile
import urllib.request
import json
from fastapi import Request

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
    
    signals = _collect_armed_signals(req_proxy, strategy_filter=None, underlying_filter=None)
    for signal_id, sig in signals:
        if sig.strategy == "scalping/price_action":
            print("Found price_action signal!")
            print(sig.model_dump())
            market = MarketContext(
                spot=sig.entry,
                underlying=sig.underlying,
            )
            decision = decide_both(
                signal=sig,
                market=market,
                profile_overrides=overrides
            )
            print("Decision status:", decision.status)
            print("Decision reason:", decision.reason)
            print("Futures candidate:", bool(decision.futures))

asyncio.run(trace())
