import asyncio
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals, _market_context, _option_chain_or_none, _decide_both
from app.engines.derivatives.profiles import StrategyDerivativesProfile
import urllib.request
import json
from fastapi import Request
from app.engines.derivatives.schemas import DecisionStatus

class DummyApp:
    state = type("State", (), {})()
    
class DummyRequest:
    app = DummyApp()

async def trace():
    req = urllib.request.Request("http://localhost:8000/api/v1/derivatives/config")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        
    req_proxy = DummyRequest()
    req_proxy.app.state.derivatives_profile_overrides = {
        k: StrategyDerivativesProfile(**v) for k, v in data["profiles"].items()
    }
    
    signals = await asyncio.to_thread(
        _collect_armed_signals, req_proxy,
        strategy_filter=None, underlying_filter="ETH",
    )
    print("Signals collected:", len(signals))
    
    for signal_id, sig in signals:
        try:
            market = await _market_context(
                underlying=sig.underlying, app=req_proxy.app,
                signal_score=sig.signal_score,
            )
        except Exception as e:
            print("Market error:", e)
            continue
            
        try:
            chain = await _option_chain_or_none(
                underlying=sig.underlying, app=req_proxy.app, spot=market.spot,
            )
        except Exception as e:
            print("Chain error:", e)
            chain = None
            
        dual = _decide_both(
            signal=sig, market=market, chain=chain,
            profile_overrides=req_proxy.app.state.derivatives_profile_overrides,
        )
        print("Futures Status:", dual.futures.status if dual.futures else "None")
        print("Futures Reason:", dual.futures.reason if dual.futures else "None")
        print("Options Status:", dual.options.status if dual.options else "None")
        print("Options Reason:", dual.options.reason if dual.options else "None")
        
asyncio.run(trace())
