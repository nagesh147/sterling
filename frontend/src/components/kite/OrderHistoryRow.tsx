import React from 'react';
import { useKiteOrderHistory, useKiteOrderTrades } from '../../hooks/useKite';

const num = (v: any) => Number(v ?? 0);

export function OrderHistoryRow({ orderId, colSpan }: { orderId: string; colSpan: number }) {
  const { data: history } = useKiteOrderHistory(orderId);
  const { data: trades } = useKiteOrderTrades(orderId);

  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: '10px 24px', background: 'var(--k-surface-2)', borderBottom: '1px solid var(--k-surface-hover)' }}>
        <div style={{ display: 'flex', gap: 32, fontSize: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ color: 'var(--k-dim)', marginBottom: 6, fontSize: 11 }}>Status history</div>
            {(!history || history.length === 0) && <div style={{ color: 'var(--k-dim)' }}>No history yet.</div>}
            {history?.map((h: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: 'var(--k-text)' }}>
                <span>{h.status}</span>
                <span style={{ color: 'var(--k-dim)' }}>{h.order_timestamp}</span>
              </div>
            ))}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ color: 'var(--k-dim)', marginBottom: 6, fontSize: 11 }}>Fills</div>
            {(!trades || trades.length === 0) && <div style={{ color: 'var(--k-dim)' }}>No fills yet.</div>}
            {trades?.map((t: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: 'var(--k-text)' }}>
                <span>{num(t.quantity)} @ {num(t.average_price).toFixed(2)}</span>
                <span style={{ color: 'var(--k-dim)' }}>{t.fill_timestamp}</span>
              </div>
            ))}
          </div>
        </div>
      </td>
    </tr>
  );
}
