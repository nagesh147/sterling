import asyncio
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals
from app.engines.derivatives.selector import decide_both
from app.engines.derivatives.schemas import MarketContext
from app.engines.derivatives.profiles import StrategyDerivativesProfile
import urllib.request
import json

class DummyApp:
    state = type("State", (), {})()

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
    
    signals = _collect_armed_signals(req_proxy, strategy_filter=None, underlying_filter="ETH")
    for signal_id, sig in signals:
        market = MarketContext(
            spot=sig.entry,
            underlying=sig.underlying,
        )
        decision = decide_both(
            signal=sig,
            market=market,
            profile_overrides=overrides
        )
        print("Signal:", sig.strategy)
        print("Status (O):", decision.options.status if decision.options else "None")
        print("Chosen (O):", bool(decision.options.chosen) if decision.options else "None")
        print("Reason (O):", decision.options.reason if decision.options else "None")
            
asyncio.run(trace())
