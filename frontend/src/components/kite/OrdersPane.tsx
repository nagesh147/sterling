import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useCancelKiteOrder, useKiteOrders, usePlaceKiteOrder } from '../../hooks/useKite';
import type { PlaceOrderBody } from '../../types/kite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  input: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  btnBuy: { background: tint(t.green, 12), color: t.green, border: `1px solid ${t.green}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
  btnSell: { background: tint(t.red, 12), color: t.red, border: `1px solid ${t.red}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
};

const sel = (val: string, set: (v: string) => void, opts: string[]) => (
  <select style={S.input} value={val} onChange={(e) => set(e.target.value)}>
    {opts.map((o) => <option key={o} value={o}>{o}</option>)}
  </select>
);

export function OrdersPane() {
  const place = usePlaceKiteOrder();
  const cancel = useCancelKiteOrder();
  const { data: orders } = useKiteOrders(true);

  const [f, setF] = useState({
    tradingsymbol: '', exchange: 'NSE', quantity: '1', order_type: 'MARKET',
    product: 'MIS', variety: 'regular', price: '', trigger_price: '', validity: 'DAY',
  });
  const up = (k: string) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const submit = (side: 'BUY' | 'SELL') => {
    const body: PlaceOrderBody = {
      tradingsymbol: f.tradingsymbol.trim().toUpperCase(), exchange: f.exchange,
      transaction_type: side, quantity: Number(f.quantity) || 1,
      order_type: f.order_type as PlaceOrderBody['order_type'], product: f.product as PlaceOrderBody['product'],
      variety: f.variety, validity: f.validity,
      price: f.price ? Number(f.price) : null, trigger_price: f.trigger_price ? Number(f.trigger_price) : null,
    };
    place.mutate(body);
  };

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>PLACE ORDER</div>
        <div style={S.grid}>
          <div><label style={S.label}>SYMBOL</label><input style={S.input} value={f.tradingsymbol} onChange={(e) => up('tradingsymbol')(e.target.value)} placeholder="INFY" /></div>
          <div><label style={S.label}>EXCHANGE</label>{sel(f.exchange, up('exchange'), ['NSE', 'NFO', 'BSE', 'MCX', 'CDS'])}</div>
          <div><label style={S.label}>QTY</label><input style={S.input} value={f.quantity} onChange={(e) => up('quantity')(e.target.value)} /></div>
          <div><label style={S.label}>TYPE</label>{sel(f.order_type, up('order_type'), ['MARKET', 'LIMIT', 'SL', 'SL-M'])}</div>
          <div><label style={S.label}>PRODUCT</label>{sel(f.product, up('product'), ['MIS', 'CNC', 'NRML'])}</div>
          <div><label style={S.label}>VARIETY</label>{sel(f.variety, up('variety'), ['regular', 'amo', 'iceberg'])}</div>
          {(f.order_type === 'LIMIT' || f.order_type === 'SL') && (
            <div><label style={S.label}>PRICE</label><input style={S.input} value={f.price} onChange={(e) => up('price')(e.target.value)} /></div>
          )}
          {(f.order_type === 'SL' || f.order_type === 'SL-M') && (
            <div><label style={S.label}>TRIGGER</label><input style={S.input} value={f.trigger_price} onChange={(e) => up('trigger_price')(e.target.value)} /></div>
          )}
          <div><label style={S.label}>VALIDITY</label>{sel(f.validity, up('validity'), ['DAY', 'IOC'])}</div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
          <button style={S.btnBuy} disabled={!f.tradingsymbol.trim() || place.isPending} onClick={() => submit('BUY')}>BUY</button>
          <button style={S.btnSell} disabled={!f.tradingsymbol.trim() || place.isPending} onClick={() => submit('SELL')}>SELL</button>
          {place.isSuccess && <span style={{ color: t.green, fontSize: 11, alignSelf: 'center' }}>✓ {place.data?.order_id}{place.data?.deduplicated ? ' (dedup)' : ''}</span>}
          {place.error && <span style={{ color: t.red, fontSize: 11, alignSelf: 'center' }}>✗ {place.error.message}</span>}
        </div>
      </div>

      <div style={S.card}>
        <div style={S.title}>ORDER BOOK</div>
        {(!orders || orders.length === 0) && <div style={S.hint}>No orders today.</div>}
        {orders && orders.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th><th style={S.th}>Side</th><th style={S.th}>Type</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Qty</th><th style={{ ...S.th, textAlign: 'right' }}>Price</th>
              <th style={S.th}>Status</th><th style={S.th} />
            </tr></thead>
            <tbody>
              {orders.map((o: any) => (
                <tr key={o.order_id}>
                  <td style={S.td}>{o.tradingsymbol}</td>
                  <td style={{ ...S.td, color: o.transaction_type === 'BUY' ? t.green : t.red }}>{o.transaction_type}</td>
                  <td style={S.td}>{o.order_type}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{o.quantity}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{Number(o.price ?? 0).toFixed(2)}</td>
                  <td style={{ ...S.td, color: t.dim }}>{o.status}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    {['OPEN', 'TRIGGER PENDING'].includes(o.status) && (
                      <span style={{ cursor: 'pointer', color: t.red }} onClick={() => cancel.mutate({ id: o.order_id, variety: o.variety || 'regular' })}>cancel</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
