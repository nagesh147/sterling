import React from 'react';
import { usePnlHistory } from '../hooks/usePnlHistory';
import type { PnLSnapshot } from '../hooks/usePnlHistory';

const W = 150;
const H = 32;
const PAD = 2;

function buildPath(vals: number[], min: number, range: number): string {
  const n = vals.length;
  if (n < 2) return '';
  return vals
    .map((v, i) => {
      const x = PAD + (i / (n - 1)) * (W - PAD * 2);
      const y = PAD + (1 - (v - min) / range) * (H - PAD * 2);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

interface Props { positionId: string; entrySpot: number }

export function PnLSparkline({ positionId, entrySpot }: Props) {
  const { data } = usePnlHistory(positionId);

  if (!data || data.count < 2) {
    return (
      <div style={{ color: '#444', fontSize: 10 }}>
        Monitor to track P&L history
      </div>
    );
  }

  const snaps = data.snapshots;
  const pnls = snaps.map(s => s.estimated_pnl);
  const min = Math.min(0, ...pnls);
  const max = Math.max(0, ...pnls);
  const range = max - min || 1;

  const zeroY = PAD + (1 - (0 - min) / range) * (H - PAD * 2);
  const lastPnl = pnls[pnls.length - 1];
  const lineColor = lastPnl >= 0 ? '#44cc88' : '#cc4444';
  const path = buildPath(pnls, min, range);

  return (
    <div title={`P&L history (${data.count} snapshots) | Latest: ${lastPnl >= 0 ? '+' : ''}${lastPnl.toFixed(2)}`}>
      <div style={{ color: lastPnl >= 0 ? '#44cc88' : '#cc4444', fontSize: 10, marginBottom: 2 }}>
        P&L {lastPnl >= 0 ? '+' : ''}{lastPnl.toFixed(2)}
      </div>
      <svg width={W} height={H} style={{ display: 'block' }}>
        {/* Zero line */}
        <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY}
          stroke="#333" strokeWidth="0.5" strokeDasharray="2,2" />
        {/* P&L line */}
        <path d={path} stroke={lineColor} strokeWidth="1.5" fill="none" />
        {/* Latest dot */}
        <circle
          cx={W - PAD}
          cy={PAD + (1 - (lastPnl - min) / range) * (H - PAD * 2)}
          r="2.5"
          fill={lineColor}
        />
      </svg>
    </div>
  );
}
