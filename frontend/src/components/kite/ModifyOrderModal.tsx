import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteOrder } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';

interface OrderRow {
  order_id: string;
  variety: string;
  tradingsymbol: string;
  exchange: string;
  quantity: number;
  price: number;
  trigger_price?: number;
  order_type: string;
  validity: string;
}

export function ModifyOrderModal({ order, onClose }: { order: OrderRow; onClose: () => void }) {
  const modify = useModifyKiteOrder();
  const [quantity, setQuantity] = useState(order.quantity);
  const [price, setPrice] = useState(order.price);
  const [triggerPrice, setTriggerPrice] = useState(order.trigger_price ?? 0);
  const [error, setError] = useState<string | null>(null);
  const needsPrice = order.order_type === 'LIMIT' || order.order_type === 'SL';
  const needsTrigger = order.order_type === 'SL' || order.order_type === 'SL-M';

  const submit = () => {
    setError(null);
    if (!(quantity > 0)) { setError('Enter a quantity greater than 0'); return; }
    if (quantity > order.quantity) { setError(`Quantity can only be reduced, not increased above ${order.quantity}`); return; }
    if (needsPrice && !(price > 0)) { setError('Enter a valid price'); return; }
    if (needsTrigger && !(triggerPrice > 0)) { setError('Enter a valid trigger price'); return; }
    modify.mutate(
      {
        id: order.order_id, variety: order.variety, quantity, validity: order.validity,
        ...(needsPrice ? { price } : {}),
        ...(needsTrigger ? { trigger_price: triggerPrice } : {}),
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') },
    );
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>
            Modify order <InstrumentLabel symbol={`${order.exchange}:${order.tradingsymbol}`} />
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Quantity
            <input type="number" min={1} max={order.quantity} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
            <span style={{ display: 'block', marginTop: 3, fontSize: 10.5, color: '#bbb' }}>Can only be reduced, not increased above {order.quantity}</span>
          </label>
          {needsPrice && (
            <label style={{ fontSize: 12, color: '#9b9b9b' }}>Price
              <input type="number" step={0.05} value={price} onChange={(e) => setPrice(Number(e.target.value))}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
            </label>
          )}
          {needsTrigger && (
            <label style={{ fontSize: 12, color: '#9b9b9b' }}>Trigger price
              <input type="number" step={0.05} value={triggerPrice} onChange={(e) => setTriggerPrice(Number(e.target.value))}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
            </label>
          )}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={onClose} style={{ flex: 1, background: '#fff', color: '#444', border: `1px solid ${k.border}`, borderRadius: 3, padding: '9px', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
          <button onClick={submit} disabled={modify.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: modify.isPending ? 'not-allowed' : 'pointer', opacity: modify.isPending ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Modify'}
          </button>
        </div>
      </div>
    </>
  );
}
