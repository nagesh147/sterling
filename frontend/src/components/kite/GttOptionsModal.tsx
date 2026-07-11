import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteGtt, useDeleteKiteGtt } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';

export function GttOptionsModal({ gtt, onClose }: { gtt: any; onClose: () => void }) {
  const modify = useModifyKiteGtt();
  const del = useDeleteKiteGtt();
  const initialTrigger = gtt.condition?.trigger_values?.[0] ?? 0;
  const [triggerPrice, setTriggerPrice] = useState(initialTrigger);
  const [error, setError] = useState<string | null>(null);
  const leg = gtt.orders?.[0];

  const save = () => {
    setError(null);
    if (!(triggerPrice > 0)) { setError('Enter a valid trigger price'); return; }
    modify.mutate(
      {
        id: gtt.id, trigger_type: gtt.type, tradingsymbol: gtt.condition?.tradingsymbol,
        exchange: gtt.condition?.exchange, last_price: gtt.condition?.last_price,
        trigger_values: [triggerPrice], orders: gtt.orders,
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') },
    );
  };

  const remove = () => {
    if (!window.confirm(`Delete this GTT for ${gtt.condition?.tradingsymbol}?`)) return;
    del.mutate(gtt.id, { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Delete failed') });
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#444' }}>
            GTT #{gtt.id} <InstrumentLabel symbol={`${gtt.condition?.exchange}:${gtt.condition?.tradingsymbol}`} />
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: '#9b9b9b', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {leg && <div style={{ fontSize: 12, color: '#9b9b9b' }}>{leg.transaction_type} {leg.quantity} @ {leg.product}</div>}
          <label style={{ fontSize: 12, color: '#9b9b9b' }}>Trigger price
            <input type="number" step={0.05} value={triggerPrice} onChange={(e) => setTriggerPrice(Number(e.target.value))}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
          </label>
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={remove} disabled={del.isPending} style={{ background: '#fff', color: k.red, border: `1px solid ${k.red}`, borderRadius: 3, padding: '9px 16px', fontSize: 13, cursor: del.isPending ? 'not-allowed' : 'pointer' }}>Delete</button>
          <button onClick={save} disabled={modify.isPending} style={{ flex: 1, background: k.blue, color: '#fff', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: modify.isPending ? 'not-allowed' : 'pointer', opacity: modify.isPending ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Save changes'}
          </button>
        </div>
      </div>
    </>
  );
}
