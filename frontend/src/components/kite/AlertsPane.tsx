import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import {
  useKiteAlerts, useCreateKiteAlert, useModifyKiteAlert, useDeleteKiteAlerts,
  useKiteAlertHistory, useKiteInstrumentSearch,
} from '../../hooks/useKite';
import type { KiteAlert } from '../../types/kite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  input: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, boxSizing: 'border-box' as const, width: '100%' },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  btn: { background: tint(t.cyan, 12), color: t.cyan, border: `1px solid ${t.cyan}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8, alignItems: 'end' },
  pill: { padding: '1px 7px', borderRadius: 999, fontSize: 9, fontWeight: 700 },
};

const OPERATORS = ['>=', '<=', '>', '<', '=='];
const ATTRS = ['LastTradedPrice', 'High', 'Low', 'Open', 'Close', 'Volume'];

function InstrumentPicker({ value, onPick }: { value: string; onPick: (sym: string) => void }) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const { data } = useKiteInstrumentSearch(q);
  return (
    <div style={{ position: 'relative' }}>
      <input
        style={S.input}
        value={open ? q : value}
        placeholder="Search instrument…"
        onFocus={() => { setOpen(true); setQ(''); }}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
      />
      {open && (data?.instruments?.length ?? 0) > 0 && (
        <div style={{ position: 'absolute', zIndex: 20, top: '100%', left: 0, right: 0, maxHeight: 220, overflow: 'auto', background: t.surface, border: `1px solid ${t.border}`, borderRadius: 6, marginTop: 2 }}>
          {data!.instruments.slice(0, 15).map((ins) => {
            const sym = `${ins.exchange}:${ins.tradingsymbol}`;
            return (
              <div
                key={`${sym}-${ins.instrument_token}`}
                style={{ padding: '6px 9px', fontSize: 12, cursor: 'pointer', color: t.bright, borderBottom: `1px solid ${tint(t.border, 40)}` }}
                onMouseDown={() => { onPick(sym); setOpen(false); }}
              >
                <span style={{ fontWeight: 600 }}>{ins.tradingsymbol}</span>
                <span style={{ color: t.dim, marginLeft: 6, fontSize: 10 }}>{ins.exchange} · {ins.name}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AlertHistory({ uuid }: { uuid: string }) {
  const { data, isLoading } = useKiteAlertHistory(uuid);
  if (isLoading) return <div style={{ ...S.hint, padding: '6px 8px' }}>Loading history…</div>;
  if (!data || data.length === 0) return <div style={{ ...S.hint, padding: '6px 8px' }}>Never triggered yet.</div>;
  return (
    <div style={{ padding: '4px 8px 10px' }}>
      {data.map((h, i) => (
        <div key={i} style={{ fontSize: 11, color: t.dim, padding: '2px 0' }}>
          {(h.created_at as string) || '—'} · {(h.type as string) || 'triggered'}{h.order_id ? ` · order ${h.order_id}` : ''}
        </div>
      ))}
    </div>
  );
}

export function AlertsPane() {
  const { data: alerts } = useKiteAlerts(true);
  const create = useCreateKiteAlert();
  const modify = useModifyKiteAlert();
  const del = useDeleteKiteAlerts();
  const [form, setForm] = useState({
    symbol: '', attribute: 'LastTradedPrice', operator: '>=', value: '', name: '',
    mode: 'simple' as 'simple' | 'ato',
    side: 'BUY' as 'BUY' | 'SELL', qty: '1', orderType: 'MARKET', product: 'CNC', price: '',
  });
  const [openHist, setOpenHist] = useState<string | null>(null);

  const set = (k: string, v: string) => setForm((s) => ({ ...s, [k]: v } as typeof s));

  const submit = () => {
    const [exchange, tradingsymbol] = form.symbol.includes(':') ? form.symbol.split(':') : ['NSE', form.symbol];
    const name = form.name.trim() || `${tradingsymbol} ${form.operator} ${form.value}`;
    const base = {
      name,
      lhs_exchange: exchange,
      lhs_tradingsymbol: tradingsymbol,
      lhs_attribute: form.attribute,
      operator: form.operator,
      rhs_constant: Number(form.value),
    };
    const payload = form.mode === 'ato'
      ? {
          ...base, alert_type: 'ato',
          basket: [{
            exchange, tradingsymbol,
            transaction_type: form.side, quantity: Number(form.qty) || 1,
            order_type: form.orderType, product: form.product,
            ...(form.orderType === 'LIMIT' && form.price ? { price: Number(form.price) } : {}),
          }],
        }
      : base;
    create.mutate(payload, { onSuccess: () => setForm((s) => ({ ...s, value: '', name: '', price: '' })) });
  };

  const canSubmit = form.symbol.trim() && form.value.trim() && !Number.isNaN(Number(form.value)) && !create.isPending;

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto' }}>
      <div style={S.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ ...S.title, marginBottom: 0 }}>CREATE ALERT</div>
          <div style={{ display: 'flex', gap: 4, background: t.bg, borderRadius: 6, padding: 2, border: `1px solid ${t.border}` }}>
            {(['simple', 'ato'] as const).map((m) => (
              <span
                key={m}
                onClick={() => set('mode', m)}
                style={{
                  cursor: 'pointer', fontSize: 11, fontWeight: 700, padding: '3px 12px', borderRadius: 4,
                  color: form.mode === m ? t.bright : t.dim,
                  background: form.mode === m ? tint(t.cyan, 16) : 'transparent',
                }}
              >
                {m === 'simple' ? 'Notify' : 'Auto-order'}
              </span>
            ))}
          </div>
        </div>
        <div style={S.grid}>
          <div style={{ gridColumn: 'span 2' }}>
            <label style={S.label}>INSTRUMENT</label>
            <InstrumentPicker value={form.symbol} onPick={(sym) => set('symbol', sym)} />
          </div>
          <div>
            <label style={S.label}>ATTRIBUTE</label>
            <select style={S.input} value={form.attribute} onChange={(e) => set('attribute', e.target.value)}>
              {ATTRS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label style={S.label}>OPERATOR</label>
            <select style={S.input} value={form.operator} onChange={(e) => set('operator', e.target.value)}>
              {OPERATORS.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div>
            <label style={S.label}>VALUE</label>
            <input style={S.input} value={form.value} onChange={(e) => set('value', e.target.value)} placeholder="1500" />
          </div>
        </div>

        {form.mode === 'ato' && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${tint(t.border, 60)}` }}>
            <div style={{ ...S.label, marginBottom: 8, color: t.amber }}>ORDER TO FIRE WHEN TRIGGERED</div>
            <div style={S.grid}>
              <div>
                <label style={S.label}>SIDE</label>
                <select style={S.input} value={form.side} onChange={(e) => set('side', e.target.value)}>
                  {['BUY', 'SELL'].map((x) => <option key={x}>{x}</option>)}
                </select>
              </div>
              <div><label style={S.label}>QTY</label><input style={S.input} value={form.qty} onChange={(e) => set('qty', e.target.value)} placeholder="1" /></div>
              <div>
                <label style={S.label}>ORDER TYPE</label>
                <select style={S.input} value={form.orderType} onChange={(e) => set('orderType', e.target.value)}>
                  {['MARKET', 'LIMIT'].map((x) => <option key={x}>{x}</option>)}
                </select>
              </div>
              <div>
                <label style={S.label}>PRODUCT</label>
                <select style={S.input} value={form.product} onChange={(e) => set('product', e.target.value)}>
                  {['CNC', 'MIS', 'NRML'].map((x) => <option key={x}>{x}</option>)}
                </select>
              </div>
              {form.orderType === 'LIMIT' && (
                <div><label style={S.label}>LIMIT PRICE</label><input style={S.input} value={form.price} onChange={(e) => set('price', e.target.value)} placeholder="1500" /></div>
              )}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
          <button style={{ ...S.btn, opacity: canSubmit ? 1 : 0.5, cursor: canSubmit ? 'pointer' : 'not-allowed' }} disabled={!canSubmit} onClick={submit}>
            {create.isPending ? 'CREATING…' : form.mode === 'ato' ? 'CREATE AUTO-ORDER ALERT' : 'CREATE ALERT'}
          </button>
          {create.isSuccess && <span style={{ color: t.green, fontSize: 11 }}>✓ Alert created</span>}
          {create.error && <span style={{ color: t.red, fontSize: 11 }}>✗ {create.error.message}</span>}
        </div>
        <div style={{ ...S.hint, marginTop: 8 }}>
          {form.mode === 'ato'
            ? 'Auto-order (ATO): Kite places the order above automatically when the condition is met. Simulated on paper accounts — no real order is armed.'
            : 'Native Kite server-side alerts — they trigger even when Sterling is closed, firing once the chosen attribute crosses your threshold.'}
        </div>
      </div>

      <div style={S.card}>
        <div style={S.title}>ALERTS ({alerts?.length || 0})</div>
        {(!alerts || alerts.length === 0) && <div style={S.hint}>No alerts yet.</div>}
        {alerts && alerts.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Name</th><th style={S.th}>Condition</th><th style={S.th}>Status</th>
              <th style={{ ...S.th, textAlign: 'right' }} />
            </tr></thead>
            <tbody>
              {alerts.map((a: KiteAlert) => {
                const enabled = (a.status || '').toLowerCase() === 'enabled';
                const cond = `${a.lhs_tradingsymbol ?? ''} ${a.lhs_attribute ?? ''} ${a.operator ?? ''} ${a.rhs_constant ?? ''}`.trim();
                const isOpen = openHist === a.uuid;
                return (
                  <React.Fragment key={a.uuid}>
                    <tr>
                      <td style={S.td}>{a.name}</td>
                      <td style={{ ...S.td, color: t.dim }}>{cond}</td>
                      <td style={S.td}>
                        <span style={{ ...S.pill, color: enabled ? t.green : t.dim, background: tint(enabled ? t.green : t.dim, 14) }}>
                          {a.status || 'unknown'}
                        </span>
                      </td>
                      <td style={{ ...S.td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <span style={{ cursor: 'pointer', color: t.blue, fontSize: 11, marginRight: 12 }}
                          onClick={() => setOpenHist(isOpen ? null : a.uuid)}>
                          {isOpen ? 'hide' : 'history'}
                        </span>
                        <span style={{ cursor: 'pointer', color: t.amber, fontSize: 11, marginRight: 12 }}
                          onClick={() => modify.mutate({
                            uuid: a.uuid,
                            // Kite's modify replaces the whole definition — resend it with the flipped status.
                            name: a.name,
                            lhs_exchange: a.lhs_exchange,
                            lhs_tradingsymbol: a.lhs_tradingsymbol,
                            lhs_attribute: a.lhs_attribute,
                            operator: a.operator,
                            rhs_constant: a.rhs_constant,
                            status: enabled ? 'disabled' : 'enabled',
                          })}>
                          {enabled ? 'disable' : 'enable'}
                        </span>
                        <span style={{ cursor: 'pointer', color: t.red, fontSize: 11 }}
                          onClick={() => del.mutate([a.uuid])}>
                          {del.isPending ? '…' : 'delete'}
                        </span>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr><td colSpan={4} style={{ background: t.bg, padding: 0 }}><AlertHistory uuid={a.uuid} /></td></tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default AlertsPane;
