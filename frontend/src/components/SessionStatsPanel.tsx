import React from 'react';
import { useSessionStats } from '../hooks/useSessionStats';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 14, marginBottom: 12 },
  title: { color: '#888', fontSize: 10, letterSpacing: 2, marginBottom: 10 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 },
  cell: { display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'center' },
  key: { color: '#555', fontSize: 9, letterSpacing: 1, textAlign: 'center' },
  val: { fontSize: 18, fontWeight: 700, textAlign: 'center' },
  divider: { width: 1, background: '#1e1e1e', margin: '0 4px' },
  underlyings: { display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  chip: { background: '#1a1a2a', border: '1px solid #334', borderRadius: 3, padding: '1px 7px', fontSize: 10, color: '#88aaff' },
};

export function SessionStatsPanel() {
  const { data } = useSessionStats();
  if (!data) return null;

  const hasActivity = data.total_arrows > 0 || data.run_once_total > 0 ||
    data.paper_positions_open > 0 || data.paper_positions_partially_closed > 0 || data.alerts_triggered > 0;

  if (!hasActivity) return null;  // hide when nothing has happened yet

  return (
    <div style={S.card}>
      <div style={S.title}>SESSION ACTIVITY</div>
      <div style={S.grid}>
        <div style={S.cell}>
          <span style={S.key}>▲ ARROWS</span>
          <span style={{ ...S.val, color: '#44cc88' }}>{data.green_arrows}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>▼ ARROWS</span>
          <span style={{ ...S.val, color: '#cc4444' }}>{data.red_arrows}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>RUN-ONCE</span>
          <span style={{ ...S.val, color: '#88aaff' }}>{data.run_once_total}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>CONF LONG</span>
          <span style={{ ...S.val, color: '#44cc88', fontSize: 14 }}>{data.confirmed_long_setups}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>CONF SHORT</span>
          <span style={{ ...S.val, color: '#cc4444', fontSize: 14 }}>{data.confirmed_short_setups}</span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>PARTIAL CLOSE</span>
          <span style={{ ...S.val, color: data.paper_positions_partially_closed > 0 ? '#f0c040' : '#333', fontSize: 14 }}>
            {data.paper_positions_partially_closed}
          </span>
        </div>
        <div style={S.cell}>
          <span style={S.key}>FIRED</span>
          <span style={{ ...S.val, color: data.alerts_triggered > 0 ? '#f0a500' : '#555', fontSize: 14 }}>
            {data.alerts_triggered}
          </span>
        </div>
      </div>
      {data.underlyings_with_arrows.length > 0 && (
        <div style={S.underlyings}>
          <span style={{ ...S.key, marginTop: 2 }}>ARROWS IN:</span>
          {data.underlyings_with_arrows.map(u => <span key={u} style={S.chip}>{u}</span>)}
        </div>
      )}
    </div>
  );
}
