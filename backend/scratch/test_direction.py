from app.schemas.execution import TradeStructure, CandidateContract, Direction as ExecDir, SizedTrade
import json

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
    
    print("Direction:", structure.direction.value)
    
test()
