import asyncio
from fastapi import Request
from main import app
from app.api.v1.endpoints.derivatives import _both_rows, _collect_armed_signals, _profile_overrides, get_profile, _market_context, _option_chain_or_none, _decide_both
from fastapi import HTTPException

class MockRequest:
    def __init__(self, app):
        self.app = app

async def main():
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    app.state.algo_mode = True
    req = MockRequest(app)
    
    print("Running debug _both_rows...")
    try:
        signals = await asyncio.to_thread(_collect_armed_signals, req, strategy_filter=None, underlying_filter=None)
        overrides = _profile_overrides(app)
        print(f"Got {len(signals)} signals")
        
        market_cache = {}
        chain_cache = {}
        for signal_id, sig in signals:
            prof = overrides.get(sig.strategy) or get_profile(sig.strategy)
            if not prof.enabled:
                print(f"Skipping {signal_id} because profile is disabled")
                continue
                
            ul = sig.underlying.upper()
            if ul not in market_cache:
                try:
                    market_cache[ul] = await _market_context(
                        underlying=ul, app=app, signal_score=sig.signal_score
                    )
                except HTTPException as e:
                    print(f"Skipping {signal_id} due to HTTPException: {e.detail}")
                    continue
                except Exception as e:
                    print(f"Skipping {signal_id} due to market error: {e}")
                    continue
                    
            if ul not in chain_cache:
                chain_cache[ul] = await _option_chain_or_none(
                    underlying=ul, app=app, spot=market_cache[ul].spot
                )
                
            dual = _decide_both(
                signal=sig, market=market_cache[ul], chain=chain_cache[ul],
                profile_overrides=overrides
            )
            print(f"Dual decision for {signal_id}: Futures: {dual.futures.status if dual.futures else 'None'}, Options: {dual.options.status if dual.options else 'None'}")
            if dual.futures and hasattr(dual.futures, 'reason'): print("Futures reason:", dual.futures.reason)
            if dual.options and hasattr(dual.options, 'reason'): print("Options reason:", dual.options.reason)
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
