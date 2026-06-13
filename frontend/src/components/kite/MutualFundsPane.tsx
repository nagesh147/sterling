import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import {
  useKiteMfHoldings, useKiteMfOrders, useKiteMfSips, usePlaceKiteMfOrder, useCancelKiteMfOrder,
  usePlaceKiteMfSip, useModifyKiteMfSip, useCancelKiteMfSip, useKiteMfInstrumentSearch,
} from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  input: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '7px 9px', fontFamily: 'inherit', fontSize: 12, boxSizing: 'border-box' as const },
  label: { color: t.dim, fontSize: 10, letterSpacing: 1, marginBottom: 3, display: 'block' },
  btn: { background: tint(t.cyan, 12), color: t.cyan, border: `1px solid ${t.cyan}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12, fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 },
};

const num = (v: any) => Number(v ?? 0);
const pnlCol = (v: number) => (v > 0 ? t.green : v < 0 ? t.red : t.dim);

// Mutual-fund scheme autocomplete (search the MF master by name/AMC/symbol).
function MfFundPicker({ value, onPick }: { value: string; onPick: (sym: string, name: string) => void }) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const { data } = useKiteMfInstrumentSearch(q);
  return (
    <div style={{ position: 'relative' }}>
      <input
        style={S.input}
        value={open ? q : value}
        placeholder="Search fund…"
        onFocus={() => { setOpen(true); setQ(''); }}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
      />
      {open && (data?.instruments?.length ?? 0) > 0 && (
        <div style={{ position: 'absolute', zIndex: 20, top: '100%', left: 0, right: 0, maxHeight: 220, overflow: 'auto', background: t.surface, border: `1px solid ${t.border}`, borderRadius: 6, marginTop: 2 }}>
          {data!.instruments.slice(0, 15).map((f) => (
            <div
              key={f.tradingsymbol}
              style={{ padding: '6px 9px', fontSize: 12, cursor: 'pointer', color: t.bright, borderBottom: `1px solid ${tint(t.border, 40)}` }}
              onMouseDown={() => { onPick(f.tradingsymbol, f.name || f.tradingsymbol); setOpen(false); }}
            >
              <span style={{ fontWeight: 600 }}>{f.name || f.tradingsymbol}</span>
              <span style={{ color: t.dim, marginLeft: 6, fontSize: 10 }}>{f.amc} · {f.plan}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function MutualFundsPane() {
  const { data: holdings } = useKiteMfHoldings(true);
  const { data: orders } = useKiteMfOrders(true);
  const { data: sips } = useKiteMfSips(true);
  const placeMf = usePlaceKiteMfOrder();
  const cancelMf = useCancelKiteMfOrder();
  const placeSip = usePlaceKiteMfSip();
  const modifySip = useModifyKiteMfSip();
  const cancelSip = useCancelKiteMfSip();
  const [mf, setMf] = useState({ tradingsymbol: '', transaction_type: 'BUY', amount: '', quantity: '' });
  const [sip, setSip] = useState({ tradingsymbol: '', fundName: '', amount: '', frequency: 'monthly', instalments: '' });

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>PLACE MF ORDER</div>
        <div style={S.grid}>
          <div><label style={S.label}>FUND/ISIN</label><input style={S.input} value={mf.tradingsymbol} onChange={(e) => setMf((s) => ({ ...s, tradingsymbol: e.target.value }))} placeholder="e.g. INF209K01XI3" /></div>
          <div><label style={S.label}>TYPE</label>
            <select style={S.input} value={mf.transaction_type} onChange={(e) => setMf((s) => ({ ...s, transaction_type: e.target.value }))}>
              {['BUY', 'SELL'].map((x) => <option key={x}>{x}</option>)}
            </select>
          </div>
          <div><label style={S.label}>AMOUNT (₹)</label><input style={S.input} value={mf.amount} onChange={(e) => setMf((s) => ({ ...s, amount: e.target.value, quantity: '' }))} placeholder="500" /></div>
          <div><label style={S.label}>OR QTY (units)</label><input style={S.input} value={mf.quantity} onChange={(e) => setMf((s) => ({ ...s, quantity: e.target.value, amount: '' }))} placeholder="10" /></div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
          <button
            style={S.btn}
            disabled={!mf.tradingsymbol.trim() || (!mf.amount.trim() && !mf.quantity.trim()) || placeMf.isPending}
            onClick={() => placeMf.mutate({
              tradingsymbol: mf.tradingsymbol.trim(),
              transaction_type: mf.transaction_type,
              ...(mf.amount.trim() ? { amount: Number(mf.amount) } : { quantity: Number(mf.quantity) || 1 }),
            })}
          >PlACE ORDER</button>
          {placeMf.isSuccess && <span style={{ color: t.green, fontSize: 11 }}>✓ Order placed</span>}
          {placeMf.error && <span style={{ color: t.red, fontSize: 11 }}>✗ {placeMf.error.message}</span>}
        </div>
        <div style={{ ...S.hint, marginTop: 8 }}>Orders execute at next NAV. Use either amount (₹) or quantity (units), not both.</div>
      </div>

      <div style={S.card}>
        <div style={S.title}>MF HOLDINGS</div>
        {(!holdings || holdings.length === 0) && <div style={S.hint}>No mutual fund holdings.</div>}
        {holdings && holdings.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Fund</th><th style={{ ...S.th, textAlign: 'right' }}>Units</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Avg</th><th style={{ ...S.th, textAlign: 'right' }}>LTP</th>
              <th style={{ ...S.th, textAlign: 'right' }}>P&L</th>
            </tr></thead>
            <tbody>
              {holdings.map((h: any, i: number) => {
                const pnl = num(h.pnl);
                return (
                  <tr key={h.tradingsymbol || h.folio || i}>
                    <td style={S.td}>{h.fund || h.tradingsymbol}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(h.quantity)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(h.average_price).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(h.last_price).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right', color: pnlCol(pnl), fontWeight: 700 }}>{pnl.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div style={S.card}>
        <div style={S.title}>MF ORDERS</div>
        {(!orders || orders.length === 0) && <div style={S.hint}>No mutual fund orders.</div>}
        {orders && orders.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Fund</th><th style={S.th}>Type</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Amount</th><th style={S.th}>Status</th><th style={S.th} />
            </tr></thead>
            <tbody>
              {orders.map((o: any, i: number) => (
                <tr key={o.order_id || i}>
                  <td style={S.td}>{o.fund || o.tradingsymbol}</td>
                  <td style={{ ...S.td, color: o.transaction_type === 'BUY' ? t.green : t.red }}>{o.transaction_type}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{num(o.amount).toFixed(2)}</td>
                  <td style={{ ...S.td, color: t.dim }}>{o.status}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>
                    {o.status === 'OPEN' && (
                      <span style={{ cursor: 'pointer', color: t.red }} onClick={() => cancelMf.mutate(o.order_id)}>
                        {cancelMf.isPending ? '…' : 'cancel'}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={S.card}>
        <div style={S.title}>START SIP</div>
        <div style={S.grid}>
          <div style={{ gridColumn: 'span 2' }}>
            <label style={S.label}>FUND</label>
            <MfFundPicker value={sip.fundName || sip.tradingsymbol} onPick={(sym, name) => setSip((s) => ({ ...s, tradingsymbol: sym, fundName: name }))} />
          </div>
          <div><label style={S.label}>AMOUNT (₹)</label><input style={S.input} value={sip.amount} onChange={(e) => setSip((s) => ({ ...s, amount: e.target.value }))} placeholder="1000" /></div>
          <div><label style={S.label}>FREQUENCY</label>
            <select style={S.input} value={sip.frequency} onChange={(e) => setSip((s) => ({ ...s, frequency: e.target.value }))}>
              {['weekly', 'monthly', 'quarterly'].map((x) => <option key={x}>{x}</option>)}
            </select>
          </div>
          <div><label style={S.label}>INSTALMENTS</label><input style={S.input} value={sip.instalments} onChange={(e) => setSip((s) => ({ ...s, instalments: e.target.value }))} placeholder="∞" /></div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center' }}>
          <button
            style={S.btn}
            disabled={!sip.tradingsymbol.trim() || !sip.amount.trim() || placeSip.isPending}
            onClick={() => placeSip.mutate({
              tradingsymbol: sip.tradingsymbol.trim(),
              amount: Number(sip.amount),
              frequency: sip.frequency,
              instalments: sip.instalments.trim() ? Number(sip.instalments) : -1,
            }, { onSuccess: () => setSip({ tradingsymbol: '', fundName: '', amount: '', frequency: 'monthly', instalments: '' }) })}
          >{placeSip.isPending ? 'STARTING…' : 'START SIP'}</button>
          {placeSip.isSuccess && <span style={{ color: t.green, fontSize: 11 }}>✓ SIP started</span>}
          {placeSip.error && <span style={{ color: t.red, fontSize: 11 }}>✗ {placeSip.error.message}</span>}
        </div>
        <div style={{ ...S.hint, marginTop: 8 }}>Blank instalments = run until cancelled. SIP debits execute at the next cycle's NAV.</div>
      </div>

      <div style={S.card}>
        <div style={S.title}>ACTIVE SIPs</div>
        {(!sips || sips.length === 0) && <div style={S.hint}>No active SIPs.</div>}
        {sips && sips.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Fund</th><th style={{ ...S.th, textAlign: 'right' }}>Amount</th>
              <th style={S.th}>Frequency</th><th style={S.th}>Status</th><th style={{ ...S.th, textAlign: 'right' }} />
            </tr></thead>
            <tbody>
              {sips.map((s: any, i: number) => {
                const paused = (s.status || '').toUpperCase() === 'PAUSED';
                return (
                  <tr key={s.sip_id || i}>
                    <td style={S.td}>{s.fund || s.tradingsymbol}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(s.instalment_amount || s.amount).toFixed(2)}</td>
                    <td style={S.td}>{s.frequency}</td>
                    <td style={{ ...S.td, color: paused ? t.amber : t.dim }}>{s.status}</td>
                    <td style={{ ...S.td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <span style={{ cursor: 'pointer', color: t.amber, fontSize: 11, marginRight: 12 }}
                        onClick={() => modifySip.mutate({ id: s.sip_id, status: paused ? 'active' : 'paused' })}>
                        {paused ? 'resume' : 'pause'}
                      </span>
                      <span style={{ cursor: 'pointer', color: t.red, fontSize: 11 }}
                        onClick={() => cancelSip.mutate(s.sip_id)}>
                        {cancelSip.isPending ? '…' : 'cancel'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
