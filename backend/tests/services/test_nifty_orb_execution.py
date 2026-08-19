import asyncio

from app.services.nifty_orb_execution import _conservative_quantity, _resolve_fill


class FakeClient:
    def __init__(self):
        self.history_calls = 0

    async def get_order_history(self, order_id):
        self.history_calls += 1
        return [{
            "order_id": order_id,
            "status": "PARTIALLY FILLED",
            "filled_quantity": 75,
            "average_price": 102.5,
        }]

    async def get_order_trades(self, order_id):
        return []


def test_execution_protection_uses_actual_filled_quantity():
    client = FakeClient()
    filled, average, status = asyncio.run(_resolve_fill(client, "OID", timeout_s=0.1))
    assert filled == 75
    assert average == 102.5
    assert status == "PARTIALLY FILLED"


def test_conservative_quantity_uses_full_premium_loss_ceiling():
    assert _conservative_quantity(requested=150, lot_size=75, ask=40.0, max_risk_inr=3000) == 75


def test_conservative_quantity_blocks_lot_above_budget():
    assert _conservative_quantity(requested=75, lot_size=75, ask=40.01, max_risk_inr=3000) == 0


def test_conservative_quantity_never_breaks_lot_alignment():
    assert _conservative_quantity(requested=225, lot_size=75, ask=10.0, max_risk_inr=1600) == 150


def test_invalid_quote_cannot_produce_quantity():
    assert _conservative_quantity(requested=75, lot_size=75, ask=0, max_risk_inr=3000) == 0
