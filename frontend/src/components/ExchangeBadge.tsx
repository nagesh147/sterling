import React from 'react';
import { useAccountInfo } from '../hooks/useAccount';
import { c as t, tint } from '../styles/terminalUI';

const EXCHANGE_COLORS: Record<string, string> = {
  zerodha: t.blue,
};

export function ExchangeBadge() {
  const { data } = useAccountInfo();

  if (!data?.active) {
    return (
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        background: t.raised, border: `1px solid ${t.border}`,
        borderRadius: 4, padding: '4px 10px', fontSize: 11, color: t.dim,
      }}>
        NO EXCHANGE
      </div>
    );
  }

  const color = EXCHANGE_COLORS[data.exchange_name ?? ''] ?? t.dim;

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: tint(color, 7), border: `1px solid ${tint(color, 40)}`,
      borderRadius: 4, padding: '4px 10px', fontSize: 11,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: color, display: 'inline-block',
      }} />
      <span style={{ color, fontWeight: 600 }}>{data.display_name}</span>
      {data.is_paper && <span style={{ color: t.dim, fontSize: 10 }}>PAPER</span>}
    </div>
  );
}
