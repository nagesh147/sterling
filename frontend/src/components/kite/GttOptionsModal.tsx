import React, { useState } from 'react';
import { k } from '../../styles/kiteUI';
import { useModifyKiteGtt, useDeleteKiteGtt } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';

interface GttLeg {
  tradingsymbol: string;
  exchange: string;
  transaction_type: 'BUY' | 'SELL';
  quantity: number;
  product: string;
  order_type: string;
  price: number;
}

interface GttRow {
  id: number;
  type: 'single' | 'two-leg';
  condition: { tradingsymbol: string; exchange: string; trigger_values: number[]; last_price: number };
  orders: GttLeg[];
}

export function GttOptionsModal({ gtt, onClose }: { gtt: GttRow; onClose: () => void }) {
  const modify = useModifyKiteGtt();
  const del = useDeleteKiteGtt();
  const isTwoLeg = gtt.type === 'two-leg';
  const initialTriggers = gtt.condition?.trigger_values?.length ? gtt.condition.trigger_values : [0];
  const [triggerPrices, setTriggerPrices] = useState<number[]>(initialTriggers);
  const [error, setError] = useState<string | null>(null);
  const legs = gtt.orders ?? [];
  const busy = modify.isPending || del.isPending;

  const setTriggerAt = (index: number, value: number) => {
    setTriggerPrices((prev) => prev.map((p, i) => (i === index ? value : p)));
  };

  const save = () => {
    setError(null);
    if (triggerPrices.some((tp) => !(tp > 0))) { setError('Enter a valid trigger price'); return; }
    modify.mutate(
      {
        id: gtt.id, trigger_type: gtt.type, tradingsymbol: gtt.condition?.tradingsymbol,
        exchange: gtt.condition?.exchange, last_price: gtt.condition?.last_price,
        trigger_values: triggerPrices, orders: gtt.orders,
      },
      { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Modify failed') },
    );
  };

  const remove = () => {
    setError(null);
    if (!window.confirm(`Delete this GTT for ${gtt.condition?.tradingsymbol}?`)) return;
    del.mutate(gtt.id, { onSuccess: onClose, onError: (err: any) => setError(err?.message || 'Delete failed') });
  };

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.06)', zIndex: 1100 }} />
      <div style={{ position: 'fixed', top: 100, left: '50%', transform: 'translateX(-50%)', width: 380, background: k.bg, borderRadius: 4, boxShadow: '0 10px 44px rgba(0,0,0,0.28)', zIndex: 1101, fontFamily: k.fontFamily }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${k.border}` }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 500, color: 'var(--k-text)' }}>
            GTT #{gtt.id} <InstrumentLabel symbol={`${gtt.condition?.exchange}:${gtt.condition?.tradingsymbol}`} />
          </h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, color: 'var(--k-dim)', cursor: 'pointer' }}>✕</button>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {legs.map((leg, i) => (
            <div key={i} style={{ fontSize: 12, color: 'var(--k-dim)' }}>{leg.transaction_type} {leg.quantity} @ {leg.product}</div>
          ))}
          {triggerPrices.map((tp, i) => (
            <label key={i} style={{ fontSize: 12, color: 'var(--k-dim)' }}>
              {isTwoLeg ? `Trigger price (leg ${i + 1})` : 'Trigger price'}
              <input type="number" step={0.05} value={tp} onChange={(e) => setTriggerAt(i, Number(e.target.value))}
                style={{ display: 'block', width: '100%', marginTop: 4, padding: '8px 10px', border: `1px solid ${k.border}`, borderRadius: 3, fontSize: 14 }} />
            </label>
          ))}
          {error && <div style={{ color: k.red, fontSize: 12 }}>{error}</div>}
        </div>
        <div style={{ display: 'flex', gap: 10, padding: '14px 18px', borderTop: `1px solid ${k.border}` }}>
          <button onClick={remove} disabled={busy} style={{ background: 'var(--k-bg)', color: k.red, border: `1px solid ${k.red}`, borderRadius: 3, padding: '9px 16px', fontSize: 13, cursor: busy ? 'not-allowed' : 'pointer' }}>Delete</button>
          <button onClick={save} disabled={busy} style={{ flex: 1, background: k.blue, color: 'var(--k-bg)', border: 'none', borderRadius: 3, padding: '9px', fontSize: 13, fontWeight: 600, cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1 }}>
            {modify.isPending ? '…' : 'Save changes'}
          </button>
        </div>
      </div>
    </>
  );
}
