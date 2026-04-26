import React from 'react';
import { useConfigInfo } from '../hooks/useConfigInfo';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 14 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 14 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 13, color: '#ccc', fontWeight: 600 },
  stack: {
    background: '#111', border: '1px solid #1e1e1e', borderRadius: 4,
    padding: '8px 12px', fontSize: 11, color: '#888', fontFamily: 'Courier New, monospace',
    marginBottom: 12,
  },
  row: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 },
  chip: {
    padding: '2px 8px', borderRadius: 3, fontSize: 11,
    background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#aaa',
  },
  chipGreen: {
    padding: '2px 8px', borderRadius: 3, fontSize: 11,
    background: '#44cc88' + '18', border: '1px solid #44cc88' + '44', color: '#44cc88',
  },
};

export function SystemInfoPanel() {
  const { data, isLoading } = useConfigInfo();

  if (isLoading) return <div style={styles.card}><div style={{ color: '#444', fontSize: 12 }}>Loading system info…</div></div>;
  if (!data) return null;

  return (
    <div style={styles.card}>
      <div style={styles.title}>SYSTEM INFO</div>

      <div style={styles.grid}>
        <div style={styles.cell}>
          <span style={styles.key}>VERSION</span>
          <span style={styles.val}>{data.version}</span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>ENVIRONMENT</span>
          <span style={{ ...styles.val, color: data.environment === 'production' ? '#f0a500' : '#44cc88' }}>
            {data.environment.toUpperCase()}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>EXCHANGE</span>
          <span style={{ ...styles.val, color: '#88aaff' }}>
            {data.exchange_adapter.toUpperCase()}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>MODE</span>
          <span style={{ ...styles.val, color: data.paper_trading ? '#44cc88' : '#cc4444' }}>
            {data.paper_trading ? '📄 PAPER' : '⚡ LIVE'}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>DEFAULT UNDERLYING</span>
          <span style={styles.val}>{data.default_underlying}</span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>DB PATH</span>
          <span style={{ ...styles.val, fontSize: 11, color: '#666', fontFamily: 'monospace' }}>
            {data.db_path.split('/').pop()}
          </span>
        </div>
      </div>

      <div style={{ ...styles.key, marginBottom: 6 }}>ADAPTER STACK</div>
      <div style={styles.stack}>{data.adapter_stack}</div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ ...styles.key, marginBottom: 6 }}>SUPPORTED UNDERLYINGS</div>
        <div style={styles.row}>
          {data.supported_underlyings.map(u => (
            <span
              key={u}
              style={data.underlyings_with_options.includes(u) ? styles.chipGreen : styles.chip}
              title={data.underlyings_with_options.includes(u) ? 'Options available' : 'No options'}
            >
              {u}
            </span>
          ))}
        </div>
        <div style={{ ...styles.key, marginTop: 4 }}>
          GREEN = options available · GRAY = spot/perp only
        </div>
      </div>

      <div style={{ marginTop: 10, display: 'flex', gap: 16, alignItems: 'center' }}>
        <a
          href="https://github.com/nagesh147/sterling"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: '#555', fontSize: 10, textDecoration: 'none' }}
        >
          ↗ github.com/nagesh147/sterling
        </a>
        <span style={{ color: '#333', fontSize: 10 }}>MIT License · Paper trading only</span>
      </div>
    </div>
  );
}
