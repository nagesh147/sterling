import React from 'react';
import { c as t, tint } from '../../styles/terminalUI';
import { useKiteMfHoldings, useKiteMfOrders, useKiteMfSips } from '../../hooks/useKite';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: t.dim, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderBottom: `1px solid ${t.border}` },
  td: { padding: '6px 8px', fontSize: 12, color: t.bright, borderBottom: `1px solid ${tint(t.border, 50)}` },
  hint: { color: t.dim, fontSize: 11 },
};

const num = (v: any) => Number(v ?? 0);
const pnlCol = (v: number) => (v > 0 ? t.green : v < 0 ? t.red : t.dim);

export function MutualFundsPane() {
  const { data: holdings } = useKiteMfHoldings(true);
  const { data: orders } = useKiteMfOrders(true);
  const { data: sips } = useKiteMfSips(true);

  return (
    <div>
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
              <th style={{ ...S.th, textAlign: 'right' }}>Amount</th><th style={S.th}>Status</th>
            </tr></thead>
            <tbody>
              {orders.map((o: any, i: number) => (
                <tr key={o.order_id || i}>
                  <td style={S.td}>{o.fund || o.tradingsymbol}</td>
                  <td style={{ ...S.td, color: o.transaction_type === 'BUY' ? t.green : t.red }}>{o.transaction_type}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{num(o.amount).toFixed(2)}</td>
                  <td style={{ ...S.td, color: t.dim }}>{o.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={S.card}>
        <div style={S.title}>SIPs</div>
        {(!sips || sips.length === 0) && <div style={S.hint}>No active SIPs.</div>}
        {sips && sips.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr>
              <th style={S.th}>Fund</th><th style={{ ...S.th, textAlign: 'right' }}>Amount</th>
              <th style={S.th}>Frequency</th><th style={S.th}>Status</th>
            </tr></thead>
            <tbody>
              {sips.map((s: any, i: number) => (
                <tr key={s.sip_id || i}>
                  <td style={S.td}>{s.fund || s.tradingsymbol}</td>
                  <td style={{ ...S.td, textAlign: 'right' }}>{num(s.instalment_amount || s.amount).toFixed(2)}</td>
                  <td style={S.td}>{s.frequency}</td>
                  <td style={{ ...S.td, color: t.dim }}>{s.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ ...S.hint, marginTop: 8 }}>Mutual fund order/SIP placement is available via API; this view is read-only for now.</div>
      </div>
    </div>
  );
}
