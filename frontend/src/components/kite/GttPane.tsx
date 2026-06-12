import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useDeleteKiteGtt, useKiteGtts, usePlaceKiteGtt } from '../../hooks/useKite';
import type { PlaceGttBody } from '../../types/kite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  input: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, width: '100%', boxSizing: 'border-box' as const },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  btn: { background: tint(t.blue, 12), color: t.blue, border: `1px solid ${t.blue}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
};

export function GttPane() {
  const { data: gtts } = useKiteGtts(true);
  const place = usePlaceKiteGtt();
  const del = useDeleteKiteGtt();
  const [f, setF] = useState({ tradingsymbol: '', exchange: 'NSE', last_price: '', trigger: '', quantity: '1', side: 'SELL', price: '', product: 'CNC' });
  const up = (k: string) => (v: string) => setF((s) => ({ ...s, [k]: v }));

  const submit = () => {
    const body: PlaceGttBody = {
      trigger_type: 'single', tradingsymbol: f.tradingsymbol.trim().toUpperCase(), exchange: f.exchange,
      last_price: Number(f.last_price) || 0, trigger_values: [Number(f.trigger) || 0],
      orders: [{
        tradingsymbol: f.tradingsymbol.trim().toUpperCase(), exchange: f.exchange,
        transaction_type: f.side as 'BUY' | 'SELL', quantity: Number(f.quantity) || 1,
        order_type: 'LIMIT', product: f.product, price: Number(f.price) || 0,
      }],
    };
    place.mutate(body);
  };

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>CREATE GTT (single trigger)</div>
        <div style={S.grid}>
          <div><label style={S.label}>SYMBOL</label><input style={S.input} value={f.tradingsymbol} onChange={(e) => up('tradingsymbol')(e.target.value)} placeholder="INFY" /></div>
          <div><label style={S.label}>EXCHANGE</label>
            <select style={S.input} value={f.exchange} onChange={(e) => up('exchange')(e.target.value)}>{['NSE', 'NFO', 'BSE'].map((x) => <option key={x}>{x}</option>)}</select>
          </div>
          <div><label style={S.label}>LAST PRICE</label><input style={S.input} value={f.last_price} onChange={(e) => up('last_price')(e.target.value)} /></div>
          <div><label style={S.label}>TRIGGER</label><input style={S.input} value={f.trigger} onChange={(e) => up('trigger')(e.target.value)} /></div>
          <div><label style={S.label}>SIDE</label>
            <select style={S.input} value={f.side} onChange={(e) => up('side')(e.target.value)}>{['SELL', 'BUY'].map((x) => <option key={x}>{x}</option>)}</select>
          </div>
          <div><label style={S.label}>QTY</label><input style={S.input} value={f.quantity} onChange={(e) => up('quantity')(e.target.value)} /></div>
          <div><label style={S.label}>LIMIT PRICE</label><input style={S.input} value={f.price} onChange={(e) => up('price')(e.target.value)} /></div>
          <div><label style={S.label}>PRODUCT</label>
            <select style={S.input} value={f.product} onChange={(e) => up('product')(e.target.value)}>{['CNC', 'NRML', 'MIS'].map((x) => <option key={x}>{x}</option>)}</select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
          <button style={S.btn} disabled={!f.tradingsymbol.trim() || place.isPending} onClick={submit}>CREATE GTT</button>
          {place.isSuccess && <span style={{ color: t.green, fontSize: 11 }}>✓ created</span>}
          {place.error && <span style={{ color: t.red, fontSize: 11 }}>✗ {place.error.message}</span>}
        </div>
      </div>

      <div style={S.card}>
        <div style={S.title}>ACTIVE GTTs</div>
        {(!gtts || gtts.length === 0) && <div style={S.hint}>No GTT triggers.</div>}
        {gtts && gtts.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr><th style={S.th}>ID</th><th style={S.th}>Symbol</th><th style={S.th}>Type</th><th style={S.th}>Status</th><th style={S.th} /></tr></thead>
            <tbody>
              {gtts.map((g: any) => (
                <tr key={g.id}>
                  <td style={S.td}>{g.id}</td>
                  <td style={S.td}>{g.condition?.tradingsymbol ?? '—'}</td>
                  <td style={S.td}>{g.type}</td>
                  <td style={{ ...S.td, color: t.dim }}>{g.status}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    <span style={{ cursor: 'pointer', color: t.red }} onClick={() => del.mutate(g.id)}>delete</span>
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
