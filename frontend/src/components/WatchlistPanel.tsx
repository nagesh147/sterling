import React, { useState } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
import type { WatchlistItem } from '../hooks/useWatchlist';
import { useStore } from '../store/useStore';
import { fmtN, fmtUSD, ivrColor, ivrWidth } from '../utils/fmt';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../utils/api';

const REGIME_COLOR: Record<string, string> = {
  bullish: '#44cc88', bearish: '#cc4444', neutral: '#888',
};
const STATE_URGENCY: Record<string, string> = {
  CONFIRMED_SETUP_ACTIVE: '#f0c040',
  ENTRY_ARMED_PULLBACK: '#44aaff',
  ENTRY_ARMED_CONTINUATION: '#66ccff',
  EARLY_SETUP_ACTIVE: '#f0a500',
  FILTERED: '#555', IDLE: '#333',
};

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: { color: '#444', textAlign: 'left', padding: '6px 10px', borderBottom: '1px solid #1e1e1e', fontSize: 11, letterSpacing: 1 },
  tr: { cursor: 'pointer', transition: 'background 0.1s' },
  td: { padding: '8px 10px', borderBottom: '1px solid #151515', color: '#ccc' },
  badge: { padding: '2px 7px', borderRadius: 3, fontSize: 11, fontWeight: 600 },
  error: { color: '#664444', fontSize: 11 },
};

function IVRBar({ ivr }: { ivr?: number | null }) {
  if (ivr == null) return <span style={{ color: '#444' }}>—</span>;
  const color = ivrColor(ivr);
  const w = ivrWidth(ivr);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 40, height: 4, background: '#222', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${w}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ color, fontSize: 11 }}>{ivr.toFixed(0)}</span>
    </div>
  );
}

function Row({ item }: { item: WatchlistItem }) {
  const { setSelectedUnderlying, selectedUnderlying } = useStore();
  const isSelected = selectedUnderlying === item.underlying;
  const stateColor = STATE_URGENCY[item.state] ?? '#444';
  const regime = item.macro_regime ?? 'neutral';

  return (
    <tr
      style={{ ...styles.tr, background: isSelected ? '#1a1a22' : 'transparent' }}
      onClick={() => setSelectedUnderlying(item.underlying)}
    >
      <td style={styles.td}>
        <span style={{ fontWeight: 700, color: isSelected ? '#aaddff' : '#e0e0e0' }}>
          {item.underlying}
        </span>
        {!item.has_options && <span style={{ color: '#444', fontSize: 10, marginLeft: 6 }}>no opts</span>}
      </td>
      <td style={styles.td}>
        {item.spot_price != null
          ? `$${fmtUSD(item.spot_price)}`
          : '—'}
      </td>
      <td style={styles.td}>
        <span style={{ color: REGIME_COLOR[regime] ?? '#888' }}>
          {regime.toUpperCase()}
        </span>
      </td>
      <td style={styles.td}>
        {item.signal_trend === 1
          ? <span style={{ color: '#44cc88' }}>▲ BULL</span>
          : item.signal_trend === -1
          ? <span style={{ color: '#cc4444' }}>▼ BEAR</span>
          : <span style={{ color: '#555' }}>~ MIX</span>}
      </td>
      <td style={styles.td}>
        <IVRBar ivr={item.ivr} />
      </td>
      <td style={styles.td}>
        <span style={{ ...styles.badge, background: stateColor + '18', color: stateColor }}>
          {item.state.replace(/_/g, ' ')}
        </span>
      </td>
      <td style={styles.td}>
        {item.score_long != null
          ? <span style={{ color: '#44cc88' }}>{item.score_long.toFixed(0)}L</span>
          : <span style={{ color: '#555' }}>—L</span>}
        {' / '}
        {item.score_short != null
          ? <span style={{ color: '#cc4444' }}>{item.score_short.toFixed(0)}S</span>
          : <span style={{ color: '#555' }}>—S</span>}
      </td>
      {item.error && <td style={styles.td}><span style={styles.error}>{item.error}</span></td>}
    </tr>
  );
}

export function WatchlistPanel() {
  const { data, isLoading, dataUpdatedAt } = useWatchlist();
  const updatedAt = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '—';
  const qc = useQueryClient();
  const [runningAll, setRunningAll] = useState(false);

  const handleRunAll = async () => {
    setRunningAll(true);
    try {
      await api.post('/api/v1/directional/run-all');
      qc.invalidateQueries({ queryKey: ['eval-history'] });
      qc.invalidateQueries({ queryKey: ['session-stats'] });
    } catch { /* ignore */ } finally {
      setRunningAll(false);
    }
  };

  return (
    <div style={styles.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={styles.title}>WATCHLIST · ALL INSTRUMENTS · {updatedAt}</div>
        <button
          style={{
            background: runningAll ? '#1a1a1a' : '#1a1a2a', color: runningAll ? '#444' : '#88aaff',
            border: `1px solid ${runningAll ? '#333' : '#88aaff'}`, padding: '5px 14px',
            borderRadius: 3, cursor: runningAll ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', fontSize: 11, letterSpacing: 1,
          }}
          onClick={handleRunAll}
          disabled={runningAll}
        >
          {runningAll ? '▶ RUNNING…' : '▶ RUN ALL'}
        </button>
      </div>
      {isLoading && <div style={{ color: '#444', fontSize: 12 }}>Loading…</div>}
      {data && (
        <table style={styles.table}>
          <thead>
            <tr>
              {['ASSET', 'SPOT', 'MACRO', '1H SIGNAL', 'IVR', 'STATE', 'SCORES'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.items.map(item => <Row key={item.underlying} item={item} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}
