import React from 'react';
import { useKiteOrderHistory, useKiteOrderTrades } from '../../hooks/useKite';

const num = (v: any) => Number(v ?? 0);

export function OrderHistoryRow({ orderId, colSpan }: { orderId: string; colSpan: number }) {
  const { data: history } = useKiteOrderHistory(orderId);
  const { data: trades } = useKiteOrderTrades(orderId);

  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: '10px 24px', background: '#fafafa', borderBottom: '1px solid #f1f1f1' }}>
        <div style={{ display: 'flex', gap: 32, fontSize: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9b9b9b', marginBottom: 6, fontSize: 11 }}>Status history</div>
            {(!history || history.length === 0) && <div style={{ color: '#9b9b9b' }}>No history yet.</div>}
            {history?.map((h: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: '#444' }}>
                <span>{h.status}</span>
                <span style={{ color: '#9b9b9b' }}>{h.order_timestamp}</span>
              </div>
            ))}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#9b9b9b', marginBottom: 6, fontSize: 11 }}>Fills</div>
            {(!trades || trades.length === 0) && <div style={{ color: '#9b9b9b' }}>No fills yet.</div>}
            {trades?.map((t: any, i: number) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', color: '#444' }}>
                <span>{num(t.quantity)} @ {num(t.average_price).toFixed(2)}</span>
                <span style={{ color: '#9b9b9b' }}>{t.fill_timestamp}</span>
              </div>
            ))}
          </div>
        </div>
      </td>
    </tr>
  );
}
