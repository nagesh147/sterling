import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useDeleteKiteGtt, useKiteGttDetail, useKiteGtts, useModifyKiteGtt, usePlaceKiteGtt } from '../../hooks/useKite';
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
  const modify = useModifyKiteGtt();
  const [form, setF] = useState({ tradingsymbol: '', exchange: 'NSE', last_price: '', trigger: '', quantity: '1', side: 'SELL', price: '', product: 'CNC' });
  const up = (k: string) => (v: string) => setF((s) => ({ ...s, [k]: v }));
  const [detailId, setDetailId] = useState<number | null>(null);
  const { data: detail } = useKiteGttDetail(detailId);
  const [editId, setEditId] = useState<number | null>(null);
  const [editTrigger, setEditTrigger] = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editLastPrice, setEditLastPrice] = useState('');

  const submit = () => {
    const body: PlaceGttBody = {
      trigger_type: 'single', tradingsymbol: form.tradingsymbol.trim().toUpperCase(), exchange: form.exchange,
      last_price: Number(form.last_price) || 0, trigger_values: [Number(form.trigger) || 0],
      orders: [{
        tradingsymbol: form.tradingsymbol.trim().toUpperCase(), exchange: form.exchange,
        transaction_type: form.side as 'BUY' | 'SELL', quantity: Number(form.quantity) || 1,
        order_type: 'LIMIT', product: form.product, price: Number(form.price) || 0,
      }],
    };
    place.mutate(body);
  };

  const startEdit = (g: any) => {
    const cond = g.condition || {};
    const order = g.orders?.[0] || {};
    setEditId(g.id);
    setEditTrigger(String(cond.trigger_values?.[0] ?? ''));
    setEditPrice(String(order.price ?? ''));
    setEditLastPrice(String(cond.last_price ?? ''));
  };

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>CREATE GTT (single trigger)</div>
        <div style={S.grid}>
          <div><label style={S.label}>SYMBOL</label><input style={S.input} value={form.tradingsymbol} onChange={(e) => up('tradingsymbol')(e.target.value)} placeholder="INFY" /></div>
          <div><label style={S.label}>EXCHANGE</label>
            <select style={S.input} value={form.exchange} onChange={(e) => up('exchange')(e.target.value)}>{['NSE', 'NFO', 'BSE'].map((x) => <option key={x}>{x}</option>)}</select>
          </div>
          <div><label style={S.label}>LAST PRICE</label><input style={S.input} value={form.last_price} onChange={(e) => up('last_price')(e.target.value)} /></div>
          <div><label style={S.label}>TRIGGER</label><input style={S.input} value={form.trigger} onChange={(e) => up('trigger')(e.target.value)} /></div>
          <div><label style={S.label}>SIDE</label>
            <select style={S.input} value={form.side} onChange={(e) => up('side')(e.target.value)}>{['SELL', 'BUY'].map((x) => <option key={x}>{x}</option>)}</select>
          </div>
          <div><label style={S.label}>QTY</label><input style={S.input} value={form.quantity} onChange={(e) => up('quantity')(e.target.value)} /></div>
          <div><label style={S.label}>LIMIT PRICE</label><input style={S.input} value={form.price} onChange={(e) => up('price')(e.target.value)} /></div>
          <div><label style={S.label}>PRODUCT</label>
            <select style={S.input} value={form.product} onChange={(e) => up('product')(e.target.value)}>{['CNC', 'NRML', 'MIS'].map((x) => <option key={x}>{x}</option>)}</select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
          <button style={S.btn} disabled={!form.tradingsymbol.trim() || place.isPending} onClick={submit}>CREATE GTT</button>
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
                <React.Fragment key={g.id}>
                  <tr>
                    <td style={S.td}>{g.id}</td>
                    <td style={S.td}>{g.condition?.tradingsymbol ?? '—'}</td>
                    <td style={S.td}>{g.type}</td>
                    <td style={{ ...S.td, color: t.dim }}>{g.status}</td>
                    <td style={{ ...S.td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <span style={{ cursor: 'pointer', color: t.blue, marginRight: 8 }} onClick={() => setDetailId(detailId === g.id ? null : g.id)}>detail</span>
                      <span style={{ cursor: 'pointer', color: t.cyan, marginRight: 8 }} onClick={() => editId === g.id ? setEditId(null) : startEdit(g)}>modify</span>
                      <span style={{ cursor: 'pointer', color: t.red }} onClick={() => del.mutate(g.id)}>delete</span>
                    </td>
                  </tr>
                  {detailId === g.id && (
                    <tr>
                      <td colSpan={5} style={{ background: tint(t.blue, 5) }}>
                        <div style={{ padding: 10, fontSize: 11 }}>
                          <div style={{ ...S.label, marginBottom: 6 }}>GTT DETAIL — ID {g.id}</div>
                          {detail && (
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8 }}>
                              <div><span style={S.label}>Status</span><span style={{ color: t.bright }}>{detail.status}</span></div>
                              <div><span style={S.label}>Trigger</span><span style={{ color: t.bright }}>{detail.condition?.trigger_values?.join(', ') ?? '—'}</span></div>
                              <div><span style={S.label}>Last price</span><span style={{ color: t.bright }}>{Number(detail.condition?.last_price ?? 0).toFixed(2)}</span></div>
                              <div><span style={S.label}>Order price</span><span style={{ color: t.bright }}>{Number(detail.orders?.[0]?.price ?? 0).toFixed(2)}</span></div>
                              <div><span style={S.label}>Created</span><span style={{ color: t.dim }}>{detail.created_at}</span></div>
                              <div><span style={S.label}>Updated</span><span style={{ color: t.dim }}>{detail.updated_at}</span></div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                  {editId === g.id && (
                    <tr>
                      <td colSpan={5} style={{ background: tint(t.cyan, 5) }}>
                        <div style={{ padding: 10, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <span style={S.hint}>Last price</span>
                          <input style={{ ...S.input, width: 100 }} value={editLastPrice} onChange={(e) => setEditLastPrice(e.target.value)} />
                          <span style={S.hint}>Trigger</span>
                          <input style={{ ...S.input, width: 100 }} value={editTrigger} onChange={(e) => setEditTrigger(e.target.value)} />
                          <span style={S.hint}>Limit price</span>
                          <input style={{ ...S.input, width: 100 }} value={editPrice} onChange={(e) => setEditPrice(e.target.value)} />
                          <button
                            style={S.btn}
                            disabled={modify.isPending}
                            onClick={() => modify.mutate({
                              id: g.id, last_price: Number(editLastPrice) || 0,
                              trigger_values: [Number(editTrigger) || 0],
                              orders: [{ ...g.orders?.[0], price: Number(editPrice) || 0 }],
                            }, { onSuccess: () => setEditId(null) })}
                          >{modify.isPending ? '…' : 'Save'}</button>
                          {modify.error && <span style={{ color: t.red, fontSize: 11 }}>✗ {modify.error.message}</span>}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
