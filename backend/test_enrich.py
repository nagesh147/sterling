import asyncio
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
from app.services.exchanges import instrument_registry
from app.engines.derivatives.selector import _build_options_candidates
from app.engines.derivatives.schemas import SignalContext, MarketContext, StrategyDerivativesProfile
from app.engines.derivatives import strike_picker
from app.api.v1.endpoints.derivatives import _option_chain_or_none
from pprint import pprint

class MockApp:
    state = type('State', (), {'adapter': None})()

async def main():
    app = MockApp()
    adapter = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=False)
    app.state.adapter = adapter
    
    inst = instrument_registry.get_instrument("ETH")
    spot = await adapter.get_spot_price(inst)
    
    chain = await _option_chain_or_none(underlying="ETH", app=app, spot=spot)
    
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
        entry=spot,
        stop_loss=spot*0.99,
        take_profit=spot*1.02,
        timestamp_ms=10000,
        score=0.9
    )
    
    mctx = MarketContext(
        spot=spot,
        underlying="ETH",
        funding_8h_pct=0.0,
        cb_size_mult=1.0,
        portfolio_value=100000
    )
    
    # Let's run strike_picker.pick manually to see the drop reasons
    from app.engines.derivatives import expiry_picker
    picked = expiry_picker.pick_expiry(chain, profile, ctx.expected_hold_minutes)
    if picked is None:
        print("Failed to pick expiry!")
        return
    dte, expiry, expiry_candidates = picked
    print(f"Picked Expiry: {expiry} (DTE {dte}), {len(expiry_candidates)} strikes")
    
    wanted_type = "call"
    expiry_filtered = [o for o in expiry_candidates if o.option_type == wanted_type]
    
    ranked = strike_picker.pick(
        candidates=expiry_filtered, profile=profile, spot=mctx.spot,
        spot_tp=ctx.take_profit, spot_sl=ctx.stop_loss,
        expected_hold_days=max(0.25, 75 / 1440.0),
        prefer_gamma=profile.expected_hold_minutes < 60 * 6,
        full_chain=chain,
    )
    
    for s in ranked:
        print(f"{s.option.instrument_name}: {s.drop_reason}")

asyncio.run(main())

    kept = [s for s in ranked if not s.drop_reason]
    
    kept_post_pin = []
    from app.engines.derivatives import pinning_gate
    for s in kept:
        pr = pinning_gate.check_pinning(s.option, mctx.spot, chain)
        if pr.veto:
            s.drop_reason = pr.reason
            print(f"Pinning veto: {s.option.instrument_name}: {s.drop_reason}")
        else:
            kept_post_pin.append(s)

    out = []
    from app.engines.derivatives import sl_tp_solver
    for rank, strike in enumerate(kept_post_pin):
        o = strike.option
        sl_plan = sl_tp_solver.solve_options(
            direction=ctx.direction, entry_spot=ctx.entry,
            stop_spot=ctx.stop_loss, target_spot=ctx.take_profit or ctx.entry,
            premium_now=strike.premium_at_tp - (strike.premium_at_tp - strike.premium_at_sl) / 2,
            premium_at_tp=strike.premium_at_tp,
            premium_at_sl=strike.premium_at_sl,
        )
        print(f"{o.instrument_name}: {sl_plan}")
