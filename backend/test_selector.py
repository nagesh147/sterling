import asyncio
import sys
import logging
from pprint import pprint

sys.path.append("/home/nageshmadaram/Sterling/backend")
from app.engines.derivatives.selector import _build_options_candidates
from app.engines.derivatives.schemas import SignalContext, MarketContext, StrategyDerivativesProfile
from app.services import adapter_manager as _adm
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges import instrument_registry as registry

class MockApp:
    state = type('State', (), {'adapter': None})()

async def main():
    app = MockApp()
    adapter = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=True)
    app.state.adapter = adapter
    _adm._active_adapter = adapter

    inst = registry.get_instrument("ETH")
    
    chain = await adapter.get_option_chain(inst)
    print(f"Got {len(chain)} option items")

    profile = StrategyDerivativesProfile(
        strategy="scalping/delta_gamma",
        min_oi=1.0,
        min_volume_24h_x_contract=1.0,
        max_spread_pct=0.05,
        target_delta=0.40,
        target_delta_tolerance=0.05,
        dte_min=0,
        dte_max=3,
        dte_preferred=1
    )

    ctx = SignalContext(
        id="test",
        underlying="ETH",
        strategy="scalping/delta_gamma",
        direction="long",
        entry=3800.0,
        stop_loss=3750.0,
        take_profit=3900.0,
        timestamp_ms=10000,
        score=0.9
    )

    mctx = MarketContext(
        spot=3800.0,
        underlying="ETH",
        funding_8h_pct=0.0,
        cb_size_mult=1.0
    )

    cands = _build_options_candidates(
        signal=ctx, 
        market=mctx, 
        profile=profile, 
        chain=chain
    )
    
    if cands:
        print(f"\nSUCCESS! Generated {len(cands)} option candidates:")
        for c in cands:
            print(f"  - {c.option_symbol} (Delta: {c.target_greeks['delta']:.2f}, R: {c.expected_r:.2f}, OI: {c.metrics.get('oi')})")
    else:
        print("\nFailed to generate options candidates.")

if __name__ == "__main__":
    asyncio.run(main())
