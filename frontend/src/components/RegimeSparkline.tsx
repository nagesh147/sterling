import React from 'react';
import { useRegimeTrend } from '../hooks/useRegimeTrend';
import type { RegimeTrendBar } from '../hooks/useRegimeTrend';

const W = 200;
const H = 36;
const PAD = 2;

function buildPath(vals: number[], min: number, range: number, n: number): string {
  return vals
    .map((v, i) => {
      const x = PAD + (i / Math.max(1, n - 1)) * (W - PAD * 2);
      const y = PAD + (1 - (v - min) / range) * (H - PAD * 2);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

interface Props { underlying: string }

export function RegimeSparkline({ underlying }: Props) {
  const { data, isLoading } = useRegimeTrend(underlying, 30);

  if (isLoading || !data || data.count < 5) {
    return (
      <svg width={W} height={H} style={{ opacity: 0.3 }}>
        <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} stroke="#333" strokeWidth="1" />
      </svg>
    );
  }

  const bars = data.bars;
  const closes = bars.map(b => b.close);
  const emas = bars.map(b => b.ema50);
  const all = [...closes, ...emas];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;
  const n = bars.length;

  const closePath = buildPath(closes, min, range, n);
  const emaPath = buildPath(emas, min, range, n);

  const last = bars[bars.length - 1];
  const lineColor = last.is_bullish ? '#44cc88' : last.regime === 'bearish' ? '#cc4444' : '#888';

  // Segments colored by regime
  const segments = bars.slice(0, -1).map((bar, i) => {
    const x1 = PAD + (i / (n - 1)) * (W - PAD * 2);
    const x2 = PAD + ((i + 1) / (n - 1)) * (W - PAD * 2);
    const y1 = PAD + (1 - (bar.close - min) / range) * (H - PAD * 2);
    const y2 = PAD + (1 - (bars[i + 1].close - min) / range) * (H - PAD * 2);
    const col = bar.is_bullish ? '#44cc88' : bar.regime === 'bearish' ? '#cc4444' : '#666';
    return { x1, y1, x2, y2, col };
  });

  return (
    <div title={`${underlying} 4H regime sparkline: ${last.regime} | Close ${last.close.toFixed(0)} EMA50 ${last.ema50.toFixed(0)}`}>
      <svg width={W} height={H} style={{ display: 'block' }}>
        {/* EMA50 line */}
        <path d={emaPath} stroke="#555" strokeWidth="1" fill="none" strokeDasharray="2,2" />
        {/* Price segments colored by regime */}
        {segments.map((s, i) => (
          <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2}
            stroke={s.col} strokeWidth="1.5" />
        ))}
        {/* Current price dot */}
        <circle
          cx={W - PAD}
          cy={PAD + (1 - (last.close - min) / range) * (H - PAD * 2)}
          r="2.5"
          fill={lineColor}
        />
      </svg>
    </div>
  );
}
