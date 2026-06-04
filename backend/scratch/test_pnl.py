from app.api.v1.endpoints.positions import _estimate_pnl, _net_delta
from app.schemas.execution import SizedTrade, TradeStructure, CandidateContract, Direction

class MockLeg:
    def __init__(self, delta):
        self.delta = delta

class MockStructure:
    def __init__(self, direction_val):
        self.direction = type('obj', (object,), {'value': direction_val})
        self.legs = [MockLeg(-1.0)]
        self.structure_type = "futures"

class MockTrade:
    def __init__(self, direction_val, qty):
        self.structure = MockStructure(direction_val)
        self.qty = qty

t = MockTrade("short", 1.0)
spot_move = -720.0
direction_sign = -1
print("net_delta:", _net_delta(t))
print("pnl:", _estimate_pnl(t, spot_move, direction_sign, 1000.0, None))
