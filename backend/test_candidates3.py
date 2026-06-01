import asyncio
from app.services import adapter_manager
from app.services.exchanges import instrument_registry as registry
from app.core.config import settings
from app.engines.derivatives.schemas import StrategyDerivativesProfile, SignalContext, MarketContext
from app.api.v1.endpoints.derivatives import _market_context, _option_chain_or_none
from app.engines.derivatives.selector import expiry_picker, strike_picker, _hold_days
from fastapi import FastAPI
import pprint

async def main():
    import logging
    logging.basicConfig(level=logging.INFO)
    
    app = FastAPI()
    
    exchange = settings.exchange_adapter.lower()
    ad = await adapter_manager.init(exchange, "test", "test")
    app.state.adapter = ad
    
    sig = SignalContext(
        strategy="scalping/delta_gamma",
        underlying="ETH",
        direction="long",
        entry=3500.0,
        stop_loss=3400.0,
        take_profit=3800.0,
        atr=100.0,
        signal_score=60.0,
    )
    
    market = await _market_context(underlying="ETH", app=app, signal_score=60.0)
    chain = await _option_chain_or_none(underlying="ETH", app=app, spot=market.spot)
    
    profile = StrategyDerivativesProfile(
        strategy="scalping/delta_gamma",
        enabled=True,
        instrument_bias="options",
        dte_preferred=1,
        dte_max=7,
        expected_hold_minutes=75,
    )
    
    picked = expiry_picker.pick_expiry(chain, profile, sig.expected_hold_minutes)
    if not picked:
        print("NO EXPIRY PICKED")
        return
    dte, expiry, expiry_candidates = picked
    wanted_type = "call" if sig.direction == "long" else "put"
    expiry_filtered = [o for o in expiry_candidates if o.option_type == wanted_type]
    
    hold_days = _hold_days(profile, sig.expected_hold_minutes)
    spot_tp = sig.take_profit or sig.entry
    spot_sl = sig.stop_loss
    
    ranked = strike_picker.pick(
        candidates=expiry_filtered, profile=profile, spot=market.spot,
        spot_tp=spot_tp, spot_sl=spot_sl,
        expected_hold_days=hold_days,
        prefer_gamma=profile.expected_hold_minutes < 60 * 6,
        full_chain=chain,
    )
    
    for s in ranked[:10]:
        print(f"Strike: {s.option.strike}, Score: {s.composite}, Drop: {s.drop_reason}")
    
    await adapter_manager.close_current()

asyncio.run(main())
