import React from 'react';
import { useArrows } from '../hooks/useArrows';
import type { ArrowEvent } from '../hooks/useArrows';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 11 },
  th: { color: '#444', textAlign: 'left', padding: '5px 10px', borderBottom: '1px solid #1e1e1e', letterSpacing: 1 },
  td: { padding: '7px 10px', borderBottom: '1px solid #141414', color: '#aaa' },
  noData: { color: '#444', fontSize: 12, padding: '20px 0', textAlign: 'center' },
  greenDot: { color: '#44cc88', fontWeight: 700 },
  redDot: { color: '#cc4444', fontWeight: 700 },
  sourceBadge: {
    fontSize: 10, padding: '1px 5px', borderRadius: 2,
    background: '#1a1a1a', color: '#555', border: '1px solid #222',
  },
};

function Row({ e }: { e: ArrowEvent }) {
  const isGreen = e.arrow_type === 'green';
  return (
    <tr>
      <td style={styles.td}>
        <span style={isGreen ? styles.greenDot : styles.redDot}>
          {isGreen ? '▲ GREEN' : '▼ RED'}
        </span>
      </td>
      <td style={styles.td}>{e.underlying}</td>
      <td style={styles.td}>${e.spot_price.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
      <td style={{ ...styles.td, color: isGreen ? '#44cc88' : '#cc4444' }}>
        {e.direction.toUpperCase()}
      </td>
      <td style={{ ...styles.td, color: '#555', fontSize: 10 }}>{e.state}</td>
      <td style={styles.td}><span style={styles.sourceBadge}>{e.source}</span></td>
      <td style={{ ...styles.td, color: '#555' }}>{new Date(e.timestamp_ms).toLocaleTimeString()}</td>
    </tr>
  );
}

interface Props { underlying: string }

export function ArrowHistoryPanel({ underlying }: Props) {
  const { data, isLoading } = useArrows(underlying);

  return (
    <div style={styles.card}>
      <div style={styles.title}>
        ARROW EVENTS · {underlying}
        {data && data.count > 0 && (
          <span style={{ color: '#555', fontWeight: 400, marginLeft: 8 }}>({data.count})</span>
        )}
      </div>

      {isLoading && <div style={styles.noData}>Loading…</div>}

      {!isLoading && (!data || data.count === 0) && (
        <div style={styles.noData}>
          No arrows recorded this session. Arrows fire when all ST trends align and flip.
        </div>
      )}

      {data && data.count > 0 && (
        <table style={styles.table}>
          <thead>
            <tr>
              {['ARROW', 'ASSET', 'SPOT', 'DIRECTION', 'STATE', 'SOURCE', 'TIME'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.arrows.map((e, i) => <Row key={i} e={e} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}
