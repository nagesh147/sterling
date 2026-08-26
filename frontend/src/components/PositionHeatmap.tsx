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

function directionLabel(raw: unknown): string {
  if (typeof raw === 'string' && raw.trim()) return raw.trim();
  if (raw && typeof raw === 'object') {
    const value = (raw as { value?: unknown }).value;
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return 'long';
}

export function PositionHeatmap({ positions, onSelect }: PositionHeatmapProps) {
  const open = positions.filter((p) => p.status === 'open' || p.status === 'partially_closed');

  if (!open.length) {
    return <div style={{ color: 'var(--k-text)', fontSize: 11, padding: '8px 0' }}>No open positions</div>;
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
      {open.map((p) => {
        const risk = p.sized_trade?.max_risk_usd ?? 1;
        const pnlRaw = (p as any).estimated_pnl_usd ?? 0;
        const pnlPct = risk > 0 ? pnlRaw / risk : 0;
        const dir = directionLabel(p.sized_trade?.structure?.direction);
        return (
          <div
            key={p.id}
            onClick={() => onSelect?.(p.id)}
            title={`${p.underlying} ${dir} | P&L: ${pnlRaw >= 0 ? '+' : ''}$${pnlRaw.toFixed(0)}`}
            style={{
              width: 70, height: 48, borderRadius: 4,
              background: pnlColor(pnlPct),
              border: '1px solid var(--k-ink-1)', cursor: 'pointer',
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              fontSize: 10, color: 'var(--k-border)',
            }}
          >
            <span style={{ fontWeight: 700 }}>{p.underlying}</span>
            <span style={{ fontSize: 9, color: 'var(--k-faint-5)' }}>{dir.toUpperCase()}</span>
            {p.exit_mode && p.current_red_count != null && p.exit_threshold != null && p.exit_threshold > 0 && (
              <div
                role="progressbar"
                aria-label={`${p.underlying} exit confirmation progress`}
                aria-valuemin={0}
                aria-valuemax={p.exit_threshold}
                aria-valuenow={Math.min(p.current_red_count, p.exit_threshold)}
                style={{ width: '90%', height: 3, background: '#222', marginTop: 2, borderRadius: 2 }}
              >
                <div style={{
                  width: `${Math.min(100, (p.current_red_count / p.exit_threshold) * 100)}%`,
                  height: '100%',
                  background: p.current_red_count >= p.exit_threshold ? '#f44' : p.current_red_count > p.exit_threshold * 0.6 ? '#fa0' : '#4a4',
                  borderRadius: 2
                }} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
