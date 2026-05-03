import React, { useState } from 'react';
import { useCandles } from '../../hooks/useCandles';
import { LiveChart } from './LiveChart';

const TFS = ['1m', '5m', '15m', '1H', '4H', 'D'];

function tfBtnStyle(active: boolean): React.CSSProperties {
  return {
    background: active ? '#1a2a1a' : 'none',
    color: active ? '#44cc88' : '#555',
    border: `1px solid ${active ? '#44cc88' : '#333'}`,
    borderRadius: 3, padding: '3px 10px', cursor: 'pointer',
    fontFamily: 'inherit', fontSize: 11,
  };
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 6, padding: 12 },
  toolbar: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' },
  statRow: {
    display: 'flex', gap: 16, fontSize: 11, color: '#666',
    marginBottom: 8, flexWrap: 'wrap',
  },
  stat: { display: 'flex', flexDirection: 'column', gap: 2 },
  key: { color: '#444', fontSize: 10 },
  val: { color: '#ccc' },
  liveDot: {
    width: 7, height: 7, borderRadius: '50%',
    background: '#44cc88', display: 'inline-block', marginRight: 4,
  },
};

interface MultiPaneChartProps {
  underlying: string;
  tf?: string;
}

export function MultiPaneChart({ underlying, tf: defaultTf = '15m' }: MultiPaneChartProps) {
  const [activeTf, setActiveTf] = useState(defaultTf);
  const { data: candles = [], isLoading } = useCandles(underlying, activeTf, 300);

  const last = candles[candles.length - 1];

  return (
    <div style={styles.wrap}>
      <div style={styles.toolbar}>
        <span style={{ color: '#888', fontWeight: 700, fontSize: 12, letterSpacing: 1 }}>
          <span style={styles.liveDot} />
          {underlying}
        </span>
        {TFS.map((tf) => (
          <button key={tf} style={tfBtnStyle(tf === activeTf)} onClick={() => setActiveTf(tf)}>
            {tf}
          </button>
        ))}
      </div>

      <div style={styles.statRow}>
        <div style={styles.stat}>
          <span style={styles.key}>SPOT</span>
          <span style={styles.val}>{last ? `$${last.close.toLocaleString()}` : '—'}</span>
        </div>
        <div style={styles.stat}>
          <span style={styles.key}>TF</span>
          <span style={styles.val}>{activeTf}</span>
        </div>
        <div style={styles.stat}>
          <span style={styles.key}>BARS</span>
          <span style={styles.val}>{candles.length}</span>
        </div>
      </div>

      {isLoading ? (
        <div style={{ color: '#444', fontSize: 11, padding: 20, textAlign: 'center' }}>
          Loading candles…
        </div>
      ) : (
        <LiveChart
          underlying={underlying}
          tf={activeTf}
          candles={candles}
          height={380}
        />
      )}
    </div>
  );
}
