import React, { useState } from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useConvertKitePosition, useKiteHoldings, useKitePositions } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
  inSm: { background: t.bg, color: t.bright, border: `1px solid ${t.border}`, borderRadius: 6, padding: '3px 6px', fontFamily: 'inherit', fontSize: 11 },
  pill: { padding: '1px 6px', borderRadius: 999, fontSize: 9, fontWeight: 700, border: `1px solid ${t.border}`, color: t.dim },
};

const num = (v: any) => Number(v ?? 0);
const pnlColor = (v: number) => (v > 0 ? t.green : v < 0 ? t.red : t.dim);

function ConvertControl({ p }: { p: any }) {
  const convert = useConvertKitePosition();
  const products = ['MIS', 'CNC', 'NRML'].filter((x) => x !== p.product);
  const [target, setTarget] = useState(products[0]);
  if (!num(p.quantity)) return null;
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'flex-end' }}>
      <select style={S.inSm} value={target} onChange={(e) => setTarget(e.target.value)}>
        {products.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <span
        style={{ cursor: 'pointer', color: convert.isError ? t.red : t.blue, fontSize: 11 }}
        title={convert.isError ? (convert.error as Error).message : `Convert ${p.product} → ${target}`}
        onClick={() => convert.mutate({
          tradingsymbol: p.tradingsymbol, exchange: p.exchange,
          transaction_type: num(p.quantity) >= 0 ? 'BUY' : 'SELL', position_type: 'day',
          quantity: Math.abs(num(p.quantity)), old_product: p.product, new_product: target,
        })}
      >
        {convert.isPending ? '…' : convert.isSuccess ? '✓' : 'convert'}
      </span>
    </div>
  );
}

export function PortfolioPane() {
  const { data: holdings } = useKiteHoldings(true);
  const { data: pos } = useKitePositions(true);
  const positions = (pos?.net ?? []).filter((p: any) => num(p.quantity) !== 0 || num(p.pnl) !== 0);

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>POSITIONS</div>
        {positions.length === 0 && <div style={S.hint}>No open positions.</div>}
        {positions.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th><th style={S.th}>Product</th><th style={S.th}>Side</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Qty</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Avg</th>
              <th style={{ ...S.th, textAlign: 'right' }}>LTP</th>
              <th style={{ ...S.th, textAlign: 'right' }}>P&L</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Convert</th>
            </tr></thead>
            <tbody>
              {positions.map((p: any, idx: number) => {
                const qty = num(p.quantity);
                return (
                  <tr key={`${p.exchange}:${p.tradingsymbol}-${idx}`}>
                    <td style={S.td}>{p.exchange}:{p.tradingsymbol}</td>
                    <td style={S.td}><span style={S.pill}>{p.product}</span></td>
                    <td style={{ ...S.td, color: qty >= 0 ? t.green : t.red }}>{qty >= 0 ? 'long' : 'short'}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{qty}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(p.average_price).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(p.last_price).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right', color: pnlColor(num(p.pnl)), fontWeight: 700 }}>{num(p.pnl).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}><ConvertControl p={p} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div style={S.card}>
        <div style={S.title}>HOLDINGS</div>
        {(!holdings || holdings.length === 0) && <div style={S.hint}>No equity holdings.</div>}
        {holdings && holdings.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Qty</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Avg</th>
              <th style={{ ...S.th, textAlign: 'right' }}>LTP</th>
              <th style={{ ...S.th, textAlign: 'right' }}>P&L</th>
            </tr></thead>
            <tbody>
              {holdings.map((h: any, idx: number) => {
                const pnl = num(h.pnl);
                return (
                  <tr key={`${h.tradingsymbol}-${idx}`}>
                    <td style={S.td}>{h.tradingsymbol}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(h.quantity)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(h.average_price).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{num(h.last_price).toFixed(2)}</td>
                    <td style={{ ...S.td, textAlign: 'right', color: pnlColor(pnl), fontWeight: 700 }}>{pnl.toFixed(2)}</td>
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
