import React from 'react';
import { useEvalHistory } from '../hooks/useEvalHistory';
import type { EvalHistoryItem } from '../hooks/useEvalHistory';
import { fmtN, fmtDateTime, ivrColor, fmtState, fmtDirection, fmtStructure } from '../utils/fmt';
import { c as t, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11 },
  th: { color: t.dim, textAlign: 'left', padding: '4px 8px', borderBottom: `1px solid ${t.border}`, letterSpacing: 1 },
  td: { padding: '5px 8px', borderBottom: `1px solid ${t.border}`, color: t.text },
  noData: { color: t.dim, fontSize: 12, padding: 12, textAlign: 'center' },
};

const STATE_COLOR: Record<string, string> = {
  CONFIRMED_SETUP_ACTIVE: t.amber, ENTRY_ARMED_PULLBACK: t.blue,
  ENTRY_ARMED_CONTINUATION: t.cyan, EARLY_SETUP_ACTIVE: t.amber,
  FILTERED: t.dim, IDLE: t.border,
};

const EXEC_META: Record<string, [string, string]> = {
  pullback:     [t.blue, 'PB'],
  continuation: [t.cyan, 'CT'],
  wait:         [t.dim,    'WT'],
};

function ExecBadge({ mode }: { mode?: string | null }) {
  if (!mode) return <span style={{ color: t.dim }}>—</span>;
  const [color, label] = EXEC_META[mode] ?? [t.dim, mode.slice(0,2).toUpperCase()];
  return (
    <span style={{ color, border: `1px solid ${color}44`, background: color + '18',
      padding: '1px 5px', borderRadius: 3, fontSize: 10 }}>{label}</span>
  );
}

function RegimeBadge({ regime }: { regime?: string | null }) {
  if (!regime) return <span style={{ color: t.dim }}>—</span>;
  const upper = regime.toUpperCase();
  const color = upper === 'VOLATILE' ? t.amber
    : upper === 'RANGING' || upper === 'CHOPPY' ? t.dim
    : upper === 'IDLE' ? '#333'
    : upper.includes('BULL') ? t.green
    : upper.includes('BEAR') ? t.red
    : t.dim;
  return (
    <span style={{
      color, background: color + '18', border: `1px solid ${color}33`,
      padding: '1px 5px', borderRadius: 3, fontSize: 9, fontWeight: 700,
    }}>{upper.slice(0, 7)}</span>
  );
}

function HistRow({ item }: { item: EvalHistoryItem }) {
  const sc = STATE_COLOR[item.state] ?? '#444';
  const dc = item.direction === 'long' ? t.green : item.direction === 'short' ? t.red : t.dim;
  return (
    <tr>
      <td style={S.td}>{fmtDateTime(item.timestamp_ms)}</td>
      <td style={{ ...S.td, color: sc, fontSize: 10 }}>{fmtState(item.state)}</td>
      <td style={{ ...S.td, color: dc, fontWeight: 600 }}>{fmtDirection(item.direction).slice(0,4)}</td>
      <td style={S.td}><RegimeBadge regime={item.macro_regime} /></td>
      <td style={S.td}>
        <span style={{ color: item.signal_trend === 1 ? t.green : item.signal_trend === -1 ? t.red : t.dim, fontWeight: 700 }}>
          {item.signal_trend === 1 ? '▲' : item.signal_trend === -1 ? '▼' : '~'}
        </span>
      </td>
      <td style={S.td}><ExecBadge mode={item.exec_mode} /></td>
      <td style={{ ...S.td, color: ivrColor(item.ivr) }}>
        {item.ivr != null ? `${item.ivr.toFixed(0)}%` : '—'}
        {item.ivr_band && <span style={{ color: t.dim, fontSize: 9 }}> {item.ivr_band.slice(0,3)}</span>}
      </td>
      <td style={{ ...S.td, fontSize: 10, color: item.top_structure ? t.blue : '#444' }}>
        {fmtStructure(item.top_structure ?? item.recommendation)}
      </td>
      <td style={{ ...S.td, color: item.no_trade_score > 50 ? t.red : t.green, fontSize: 10 }}>
        {fmtN(item.no_trade_score, 0)}
      </td>
    </tr>
  );
}

export function EvalHistoryPanel({ underlying }: { underlying: string }) {
  const { data, isLoading } = useEvalHistory(underlying);
  return (
    <div style={S.card}>
      <div style={S.title}>SIGNAL HISTORY · {underlying} · {data?.count ?? 0} runs</div>
      {isLoading && <div style={S.noData}>Loading…</div>}
      {!isLoading && data?.count === 0 && (
        <div style={S.noData}>No evaluations. Click ▶ RUN ONCE to record history.</div>
      )}
      {data && data.count > 0 && (
        <table style={S.table}>
          <thead>
            <tr>{['TIME','STATE','D','REGIME','SIG','EXEC','IVR','TOP STRUCTURE','NT'].map(h=>(
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
