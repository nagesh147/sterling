import React from 'react';
import type { PaperPosition } from '../types';

interface PositionHeatmapProps {
  positions: PaperPosition[];
  onSelect?: (id: string) => void;
}

function pnlColor(pnlPct: number): string {
  if (pnlPct > 0) return `rgba(68,204,136,${Math.min(0.9, 0.2 + Math.abs(pnlPct) * 4)})`;
  return `rgba(204,68,68,${Math.min(0.9, 0.2 + Math.abs(pnlPct) * 4)})`;
}

export function PositionHeatmap({ positions, onSelect }: PositionHeatmapProps) {
  const open = positions.filter((p) => p.status === 'open' || p.status === 'partially_closed');

  if (!open.length) {
    return <div style={{ color: '#444', fontSize: 11, padding: '8px 0' }}>No open positions</div>;
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
      {open.map((p) => {
        const risk = p.sized_trade?.max_risk_usd ?? 1;
        const pnlRaw = (p as any).estimated_pnl_usd ?? 0;
        const pnlPct = risk > 0 ? pnlRaw / risk : 0;
        const dir = p.sized_trade?.structure?.direction ?? 'long';
        return (
          <div
            key={p.id}
            onClick={() => onSelect?.(p.id)}
            title={`${p.underlying} ${dir} | P&L: ${pnlRaw >= 0 ? '+' : ''}$${pnlRaw.toFixed(0)}`}
            style={{
              width: 70, height: 48, borderRadius: 4,
              background: pnlColor(pnlPct),
              border: '1px solid #333', cursor: 'pointer',
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              fontSize: 10, color: '#e0e0e0',
            }}
          >
            <span style={{ fontWeight: 700 }}>{p.underlying}</span>
            <span style={{ fontSize: 9, color: '#ccc' }}>{dir.toUpperCase()}</span>
          </div>
        );
      })}
    </div>
  );
}
