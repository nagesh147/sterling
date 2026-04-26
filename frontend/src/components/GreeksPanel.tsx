import React from 'react';
import { usePortfolioGreeks } from '../hooks/usePortfolioGreeks';
import { fmtN } from '../utils/fmt';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 14, marginBottom: 12 },
  title: { color: '#888', fontSize: 10, letterSpacing: 2, marginBottom: 10 },
  row: { display: 'flex', gap: 20, alignItems: 'center' },
  cell: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: '#555', fontSize: 9, letterSpacing: 1 },
  val: { fontSize: 13, fontWeight: 700 },
};

export function GreeksPanel() {
  const { data } = usePortfolioGreeks();
  if (!data || data.open_positions === 0) return null;

  const deltaColor = data.total_delta > 0.05 ? '#44cc88'
    : data.total_delta < -0.05 ? '#cc4444' : '#888';
  const exposureColor = { bullish: '#44cc88', bearish: '#cc4444', neutral: '#888' }[data.net_directional_exposure];

  return (
    <div style={S.card}>
      <div style={S.title}>PAPER PORTFOLIO GREEKS</div>
      <div style={S.row}>
        <div style={S.cell}>
          <span style={S.key}>NET DELTA</span>
          <span style={{ ...S.val, color: deltaColor }}>
            {data.total_delta >= 0 ? '+' : ''}{fmtN(data.total_delta, 4)}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>EXPOSURE</span>
          <span style={{ ...S.val, color: exposureColor }}>
            {data.net_directional_exposure.toUpperCase()}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>POSITIONS</span>
          <span style={S.val}>{data.open_positions}</span>
        </div>
        <div style={{ ...S.cell, marginLeft: 'auto' }}>
          <span style={{ color: '#444', fontSize: 9 }}>
            {new Date(data.timestamp_ms).toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  );
}
