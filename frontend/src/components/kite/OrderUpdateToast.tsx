import React, { useEffect, useState } from 'react';
import { useKiteOrderUpdates, useKiteStatus } from '../../hooks/useKite';

// Listens to the live Kite order-update stream (postbacks fanned out over the
// stream WS) and shows a transient toast on every fill / cancel / rejection. Only
// active when a connected, live (non-paper) Kite session exists — paper accounts
// have no live WS, so this stays dormant for them.
export function OrderUpdateToast() {
  const { data: status } = useKiteStatus();
  const live = !!status?.connected && !status?.is_paper;
  const update = useKiteOrderUpdates(live);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!update) return;
    setVisible(true);
    const id = window.setTimeout(() => setVisible(false), 6000);
    return () => window.clearTimeout(id);
  }, [update]);

  if (!update || !visible) return null;

  const st = (update.status || '').toUpperCase();
  const color = st.includes('REJECT') || st.includes('CANCEL') ? '#e53935'
    : st.includes('COMPLETE') ? '#4caf50' : '#ff9800';
  const side = (update.transaction_type || '').toUpperCase();

  return (
    <div
      onClick={() => setVisible(false)}
      style={{
        position: 'fixed', right: 20, bottom: 20, zIndex: 1000, cursor: 'pointer',
        background: '#fff', border: `1px solid ${color}`, borderLeft: `3px solid ${color}`,
        borderRadius: 8, padding: '12px 16px', minWidth: 260, maxWidth: 360,
        boxShadow: '0 8px 24px rgba(0,0,0,0.1)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, color }}>{st || 'ORDER UPDATE'}</span>
        <span style={{ fontSize: 10, color: '#9b9b9b' }}>{update.order_id}</span>
      </div>
      <div style={{ fontSize: 13, color: '#444' }}>
        {side && <span style={{ color: side === 'BUY' ? '#4caf50' : '#e53935', fontWeight: 700, marginRight: 6 }}>{side}</span>}
        <span>{update.tradingsymbol}</span>
        {update.quantity != null && <span style={{ color: '#9b9b9b' }}> · qty {String(update.quantity)}</span>}
        {update.average_price != null && Number(update.average_price) > 0 && (
          <span style={{ color: '#9b9b9b' }}> @ {Number(update.average_price).toFixed(2)}</span>
        )}
      </div>
      <div style={{ marginTop: 6, height: 2, background: color, opacity: 0.3, borderRadius: 2 }} />
    </div>
  );
}

export default OrderUpdateToast;
