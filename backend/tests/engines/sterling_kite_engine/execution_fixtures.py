"""Broker-event fixtures. ACK and COMPLETE are deliberately separate events."""
from app.services.kite_engine import monitor, positions

async def confirm_exit(uid: str, price: float = 80.0):
    pending = [p for p in positions.open_positions(uid)
               if p.exit_order_id and p.exit_order_id not in {'unknown', 'submitting'}]
    assert pending, 'test must submit an attributable exit before confirming it'
    for p in pending:
        await monitor.on_order_update(uid, {
            'tradingsymbol':p.symbol, 'order_id':p.exit_order_id,
            'transaction_type':'SELL' if p.direction=='long' else 'BUY',
            'status':'COMPLETE', 'filled_quantity':p.qty, 'average_price':price,
        })
