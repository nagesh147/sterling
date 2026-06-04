from app.schemas.execution import TradeStructure, CandidateContract, Direction as ExecDir, SizedTrade
from app.api.v1.endpoints.positions import _estimate_pnl

def test():
    body_direction = "short"
    direction = ExecDir.LONG if body_direction == "long" else ExecDir.SHORT
    
    leg = CandidateContract(
        instrument_name="BTC-PERP",
        underlying="BTC",
        strike=67000, expiry_date="", dte=0,
        option_type="futures",
        bid=0.0, ask=0.0,
        mark_price=67000, mid_price=67000,
        mark_iv=0.0,
        delta=1.0 if body_direction == "long" else -1.0,
        open_interest=0.0, volume_24h=0.0,
        spread_pct=0.0, health_score=0.0, healthy=True,
    )
    structure = TradeStructure(
        structure_type="futures",
        direction=direction, legs=[leg],
        net_premium=67000, max_loss=67000 * 0.03,
        max_gain=None, risk_reward=2.0,
        score=0.0, score_breakdown={},
        leverage=1,
    )
    
    sized = SizedTrade(
        structure=structure,
        contracts=1000,
        contract_value=0.001, # qty = 1.0
        position_value=67000,
        max_risk_usd=1000.0,
        capital_at_risk_pct=1.0,
    )
    
    entry_spot = 67240.51
    spot = 66520.5
    spot_move = spot - entry_spot
    direction_sign = 1 if sized.structure.direction.value == "long" else -1
    
    pnl = _estimate_pnl(sized, spot_move, direction_sign, sized.max_risk_usd, sized.structure.max_gain)
    
    print(f"Structure direction: {sized.structure.direction.value}")
    print(f"Spot move: {spot_move}")
    print(f"Direction sign: {direction_sign}")
    print(f"Qty: {sized.qty}")
    print(f"PnL: {pnl}")

test()
