import React, { useState } from 'react';
import { useWatchlist } from '../hooks/useWatchlist';
import type { WatchlistItem } from '../hooks/useWatchlist';
import { useStore } from '../store/useStore';
import { SignalStrengthGauge } from './SignalStrengthGauge';
import { fmtN, fmtUSD, ivrColor, ivrWidth, fmtAge, fmtState, fmtDirection } from '../utils/fmt';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { useEnterPosition } from '../hooks/usePositions';
import { api } from '../utils/api';
import { c as t, tint } from '../styles/terminalUI';

const REGIME_COLOR: Record<string, string> = {
  bullish: t.green, bearish: t.red, neutral: t.dim,
};
const STATE_URGENCY: Record<string, string> = {
  CONFIRMED_SETUP_ACTIVE: t.amber,
  ENTRY_ARMED_PULLBACK: t.blue,
  ENTRY_ARMED_CONTINUATION: t.cyan,
  EARLY_SETUP_ACTIVE: t.amber,
  FILTERED: t.dim, IDLE: t.border2,
};

const styles: Record<string, React.CSSProperties> = {
  card: { background: t.surface, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, fontWeight: 700, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
  th: { color: t.dim, textAlign: 'left', padding: '6px 10px', borderBottom: `1px solid ${t.border}`, fontSize: 11, letterSpacing: 1 },
  tr: { cursor: 'pointer', transition: 'background 0.1s' },
  td: { padding: '8px 10px', borderBottom: `1px solid ${t.border}`, color: t.text },
  badge: { padding: '2px 7px', borderRadius: 3, fontSize: 11, fontWeight: 600 },
  error: { color: t.red, fontSize: 11 },
};

function IVRBar({ ivr }: { ivr?: number | null }) {
  if (ivr == null) return <span style={{ color: t.dim }}>—</span>;
  const color = ivrColor(ivr);
  const w = ivrWidth(ivr);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 40, height: 4, background: t.border, borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${w}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ color, fontSize: 11 }}>{ivr.toFixed(0)}</span>
    </div>
  );
}

function Row({ item }: { item: WatchlistItem }) {
  const { setSelectedUnderlying, selectedUnderlying } = useStore();
  const isSelected = selectedUnderlying === item.underlying;
  const stateColor = STATE_URGENCY[item.state] ?? t.dim;
  const regime = item.macro_regime ?? 'neutral';
  const enter = useEnterPosition();
  const isActionable = item.has_options &&
    ['CONFIRMED_SETUP_ACTIVE', 'ENTRY_ARMED_PULLBACK', 'ENTRY_ARMED_CONTINUATION'].includes(item.state);

  return (
    <tr
      style={{ ...styles.tr, background: isSelected ? t.raised : 'transparent' }}
      onClick={() => setSelectedUnderlying(item.underlying)}
    >
      <td style={styles.td}>
        <span style={{ fontWeight: 700, color: isSelected ? t.blue : t.bright }}>
          {item.underlying}
        </span>
        {!item.has_options && <span style={{ color: t.dim, fontSize: 10, marginLeft: 6 }}>no opts</span>}
      </td>
      <td style={styles.td}>
        {item.spot_price != null ? `$${fmtUSD(item.spot_price)}` : '—'}
      </td>
      <td style={styles.td}>
        <span style={{ color: REGIME_COLOR[regime] ?? t.dim }}>{regime.toUpperCase()}</span>
      </td>
      <td style={styles.td}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {item.signal_trend === 1
            ? <span style={{ color: t.green, fontSize: 10 }}>▲</span>
            : item.signal_trend === -1
            ? <span style={{ color: t.red, fontSize: 10 }}>▼</span>
            : <span style={{ color: t.dim, fontSize: 10 }}>~</span>}
          <SignalStrengthGauge
            strength={item.signal_trend === 1
              ? (item.score_long ?? 0)
              : item.signal_trend === -1
              ? (item.score_short ?? 0)
              : 0}
            size="sm"
          />
        </div>
      </td>
      <td style={styles.td}><IVRBar ivr={item.ivr} /></td>
      <td style={styles.td}>
        <span style={{ ...styles.badge, background: tint(stateColor), color: stateColor }}>
          {fmtState(item.state)}
        </span>
      </td>
      <td style={styles.td}>
        {item.score_long != null
          ? <span style={{ color: t.green }}>{item.score_long.toFixed(0)}L</span>
          : <span style={{ color: t.dim }}>—L</span>}
        {' / '}
        {item.score_short != null
          ? <span style={{ color: t.red }}>{item.score_short.toFixed(0)}S</span>
          : <span style={{ color: t.dim }}>—S</span>}
      </td>
      <td style={{ ...styles.td }} onClick={e => e.stopPropagation()}>
        {isActionable ? (
          <button
            style={{
              background: tint(t.green), color: t.green, border: `1px solid ${tint(t.green, 40)}`,
              padding: '3px 8px', borderRadius: 3, cursor: enter.isPending ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', fontSize: 10, letterSpacing: 1,
              opacity: enter.isPending ? 0.5 : 1,
            }}
            onClick={() => enter.mutate({ underlying: item.underlying })}
            disabled={enter.isPending}
            title="Paper enter position"
          >
            {enter.isPending ? '…' : '+ ENTER'}
          </button>
        ) : (
          <span style={{ color: t.border, fontSize: 10 }}>—</span>
        )}
      </td>
    </tr>
  );
}

export function WatchlistPanel() {
  const { data, isLoading, dataUpdatedAt } = useWatchlist();
  const updatedAt = dataUpdatedAt ? fmtAge(dataUpdatedAt) : '—';
  const qc = useQueryClient();

  const runAll = useMutation({
    mutationFn: () => api.post<{ instruments_evaluated: number }>('/api/v1/directional/run-all'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['eval-history'] });
      qc.invalidateQueries({ queryKey: ['session-stats'] });
      qc.invalidateQueries({ queryKey: ['watchlist'] });
    },
  });

  return (
    <div style={styles.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={styles.title}>WATCHLIST · ALL INSTRUMENTS · {updatedAt}</div>
        <button
          style={{
            background: runAll.isPending ? t.raised : tint(t.blue),
            color: runAll.isPending ? t.dim : t.blue,
            border: `1px solid ${runAll.isPending ? t.border : t.blue}`,
            padding: '5px 14px', borderRadius: 3,
            cursor: runAll.isPending ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', fontSize: 11, letterSpacing: 1,
          }}
          onClick={() => runAll.mutate()}
          disabled={runAll.isPending}
        >
          {runAll.isPending ? '▶ RUNNING…' : '▶ RUN ALL'}
        </button>
      </div>
      {isLoading && <div style={{ color: t.dim, fontSize: 12 }}>Loading…</div>}
      {data && (
        <table style={styles.table}>
          <thead>
            <tr>
              {['ASSET', 'SPOT', 'MACRO', '1H SIGNAL', 'IV RANK', 'STATUS', 'SCORES', ''].map(h => (
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
