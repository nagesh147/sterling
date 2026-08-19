import asyncio

from app.services.nifty_orb_execution import _resolve_fill


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
