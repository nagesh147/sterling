import React from 'react';
import { useEvalHistory } from '../hooks/useEvalHistory';
import type { EvalHistoryItem } from '../hooks/useEvalHistory';
import { fmtN, fmtDateTime, ivrColor } from '../utils/fmt';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11 },
  th: { color: '#444', textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #1e1e1e', letterSpacing: 1 },
  td: { padding: '5px 8px', borderBottom: '1px solid #141414', color: '#aaa' },
  noData: { color: '#444', fontSize: 12, padding: 12, textAlign: 'center' },
};

const STATE_COLOR: Record<string, string> = {
  CONFIRMED_SETUP_ACTIVE: '#f0c040', ENTRY_ARMED_PULLBACK: '#44aaff',
  ENTRY_ARMED_CONTINUATION: '#66ccff', EARLY_SETUP_ACTIVE: '#f0a500',
  FILTERED: '#555', IDLE: '#333',
};

const EXEC_META: Record<string, [string, string]> = {
  pullback:     ['#44aaff', 'PB'],
  continuation: ['#66ccff', 'CT'],
  wait:         ['#555',    'WT'],
};

function ExecBadge({ mode }: { mode?: string | null }) {
  if (!mode) return <span style={{ color: '#333' }}>—</span>;
  const [color, label] = EXEC_META[mode] ?? ['#555', mode.slice(0,2).toUpperCase()];
  return (
    <span style={{ color, border: `1px solid ${color}44`, background: color + '18',
      padding: '1px 5px', borderRadius: 3, fontSize: 10 }}>{label}</span>
  );
}

function HistRow({ item }: { item: EvalHistoryItem }) {
  const sc = STATE_COLOR[item.state] ?? '#444';
  const dc = item.direction === 'long' ? '#44cc88' : item.direction === 'short' ? '#cc4444' : '#888';
  return (
    <tr>
      <td style={S.td}>{fmtDateTime(item.timestamp_ms)}</td>
      <td style={{ ...S.td, color: sc, fontSize: 10 }}>{item.state.replace(/_/g, ' ')}</td>
      <td style={{ ...S.td, color: dc, fontWeight: 600 }}>{item.direction.slice(0,1).toUpperCase()}</td>
      <td style={S.td}>
        <span style={{ color: item.signal_trend === 1 ? '#44cc88' : item.signal_trend === -1 ? '#cc4444' : '#888', fontWeight: 700 }}>
          {item.signal_trend === 1 ? '▲' : item.signal_trend === -1 ? '▼' : '~'}
        </span>
      </td>
      <td style={S.td}><ExecBadge mode={item.exec_mode} /></td>
      <td style={{ ...S.td, color: ivrColor(item.ivr) }}>
        {item.ivr != null ? `${item.ivr.toFixed(0)}%` : '—'}
        {item.ivr_band && <span style={{ color: '#444', fontSize: 9 }}> {item.ivr_band.slice(0,3)}</span>}
      </td>
      <td style={{ ...S.td, fontSize: 10, color: item.top_structure ? '#aaddff' : '#444' }}>
        {item.top_structure ?? item.recommendation}
      </td>
      <td style={{ ...S.td, color: item.no_trade_score > 50 ? '#cc4444' : '#44cc88', fontSize: 10 }}>
        {fmtN(item.no_trade_score, 0)}
      </td>
    </tr>
  );
}

export function EvalHistoryPanel({ underlying }: { underlying: string }) {
  const { data, isLoading } = useEvalHistory(underlying);
  return (
    <div style={S.card}>
      <div style={S.title}>EVAL HISTORY · {underlying} · {data?.count ?? 0} runs</div>
      {isLoading && <div style={S.noData}>Loading…</div>}
      {!isLoading && data?.count === 0 && (
        <div style={S.noData}>No evaluations. Click ▶ RUN ONCE to record history.</div>
      )}
      {data && data.count > 0 && (
        <table style={S.table}>
          <thead>
            <tr>{['TIME','STATE','D','SIG','EXEC','IVR','TOP STRUCTURE','NT'].map(h=>(
              <th key={h} style={S.th}>{h}</th>
            ))}</tr>
          </thead>
          <tbody>
            {[...data.history].reverse().map((item, i) => <HistRow key={i} item={item} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}
