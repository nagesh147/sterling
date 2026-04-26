import React from 'react';
import { useAccountInfo } from '../hooks/useAccount';

const EXCHANGE_COLORS: Record<string, string> = {
  delta_india: '#f0a500',
  deribit: '#88aaff',
  okx: '#44cc88',
};

export function ExchangeBadge() {
  const { data } = useAccountInfo();

  if (!data?.active) {
    return (
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        background: '#1a1a1a', border: '1px solid #222',
        borderRadius: 4, padding: '4px 10px', fontSize: 11, color: '#444',
      }}>
        NO EXCHANGE
      </div>
    );
  }

  const color = EXCHANGE_COLORS[data.exchange_name ?? ''] ?? '#888';

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: color + '11', border: `1px solid ${color}44`,
      borderRadius: 4, padding: '4px 10px', fontSize: 11,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: color, display: 'inline-block',
        boxShadow: `0 0 5px ${color}`,
      }} />
      <span style={{ color, fontWeight: 600 }}>{data.display_name}</span>
      {data.is_paper && <span style={{ color: '#555', fontSize: 10 }}>PAPER</span>}
    </div>
  );
}
