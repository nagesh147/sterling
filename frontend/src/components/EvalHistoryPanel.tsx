import React from 'react';
import { useEvalHistory } from '../hooks/useEvalHistory';
import { fmtN } from '../utils/fmt';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11 },
  th: { color: '#444', textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid #1e1e1e' },
  td: { padding: '5px 8px', borderBottom: '1px solid #141414', color: '#aaa' },
  noData: { color: '#444', fontSize: 12, padding: 12, textAlign: 'center' },
};

function recColor(rec: string) {
  if (rec === 'no_trade') return '#555';
  if (rec.includes('call') || rec.includes('bull')) return '#44cc88';
  return '#cc4444';
}

interface Props { underlying: string }

export function EvalHistoryPanel({ underlying }: Props) {
  const { data, isLoading } = useEvalHistory(underlying);

  return (
    <div style={styles.card}>
      <div style={styles.title}>EVAL HISTORY · {underlying} · last {data?.count ?? 0} runs</div>
      {isLoading && <div style={styles.noData}>Loading…</div>}
      {!isLoading && data?.count === 0 && (
        <div style={styles.noData}>No evaluations yet — run /run-once to record history.</div>
      )}
      {data && data.count > 0 && (
        <table style={styles.table}>
          <thead>
            <tr>
              {['TIME', 'STATE', 'DIRECTION', 'RECOMMENDATION', 'IVR', 'NO-TRADE SCORE'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...data.history].reverse().map((item, i) => (
              <tr key={i}>
                <td style={styles.td}>{new Date(item.timestamp_ms).toLocaleTimeString()}</td>
                <td style={styles.td}>{item.state}</td>
                <td style={styles.td}>{item.direction.toUpperCase()}</td>
                <td style={{ ...styles.td, color: recColor(item.recommendation), fontWeight: 600 }}>
                  {item.recommendation}
                </td>
                <td style={styles.td}>{item.ivr != null ? `${item.ivr.toFixed(1)}%` : '—'}</td>
                <td style={styles.td}>{fmtN(item.no_trade_score, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
