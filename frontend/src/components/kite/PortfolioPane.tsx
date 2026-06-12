import React from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteHoldings, useKitePositions } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
};

const num = (v: any) => Number(v ?? 0);
const pnlColor = (v: number) => (v > 0 ? t.green : v < 0 ? t.red : t.dim);

export function PortfolioPane() {
  const { data: holdings } = useKiteHoldings(true);
  const { data: pos } = useKitePositions(true);
  const positions = pos?.positions ?? [];

  return (
    <div>
      <div style={S.card}>
        <div style={S.title}>POSITIONS</div>
        {positions.length === 0 && <div style={S.hint}>No open positions.</div>}
        {positions.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Symbol</th><th style={S.th}>Side</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Qty</th>
              <th style={{ ...S.th, textAlign: 'right' }}>Avg</th>
              <th style={{ ...S.th, textAlign: 'right' }}>LTP</th>
              <th style={{ ...S.th, textAlign: 'right' }}>P&L</th>
            </tr></thead>
            <tbody>
              {positions.map((p, idx) => (
                <tr key={`${p.symbol}-${idx}`}>
                  <td style={S.td}>{p.symbol}</td>
                  <td style={{ ...S.td, color: p.side === 'long' ? t.green : t.red }}>{p.side}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{p.size}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{num(p.entry_price).toFixed(2)}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{num(p.mark_price).toFixed(2)}</td>
                  <td style={{ ...S.td, textAlign: 'right', color: pnlColor(num(p.unrealized_pnl)), fontWeight: 700 }}>
                    {num(p.unrealized_pnl).toFixed(2)}
                  </td>
                </tr>
              ))}
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
