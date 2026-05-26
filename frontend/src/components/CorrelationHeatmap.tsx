import React from 'react';
import { useCorrelation } from '../hooks/useCorrelation';
import { c as t, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  noData: { color: t.dim, fontSize: 12 },
  warning: { color: t.amber, fontSize: 11, background: '#1a1400', border: '1px solid #f0c04033', borderRadius: 3, padding: '4px 10px', marginBottom: 8 },
};

function corrColor(v: number): string {
  const a = Math.abs(v);
  if (a > 0.8) return t.red;
  if (a > 0.6) return t.amber;
  return t.green;
}

export function CorrelationHeatmap() {
  const { data, isLoading } = useCorrelation();

  if (isLoading) return <div style={{ color: t.dim, fontSize: 11 }}>Loading…</div>;
  if (!data || data.assets.length === 0) return <div style={S.noData}>No correlation data — feed 1H closes to CorrelationTracker</div>;

  const { assets, matrix } = data;

  const highPairs: string[] = [];
  for (let i = 0; i < assets.length; i++) {
    for (let j = i + 1; j < assets.length; j++) {
      const key = `${assets[i]}:${assets[j]}`;
      const v = matrix[key] ?? 0;
      if (Math.abs(v) > 0.8) highPairs.push(`${assets[i]}/${assets[j]}: ${v.toFixed(2)}`);
    }
  }

  return (
    <div style={S.card}>
      <div style={S.title}>CROSS-ASSET CORRELATION</div>

      {highPairs.length > 0 && (
        <div style={S.warning}>High correlation: {highPairs.join(' · ')}</div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: 11 }}>
          <thead>
            <tr>
              <th style={{ color: t.dim, padding: '4px 8px' }}></th>
              {assets.map(a => (
                <th key={a} style={{ color: t.dim, padding: '4px 8px', fontWeight: 600 }}>{a}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {assets.map(rowAsset => (
              <tr key={rowAsset}>
                <td style={{ color: t.dim, padding: '4px 8px', fontWeight: 600 }}>{rowAsset}</td>
                {assets.map(colAsset => {
                  const key = `${rowAsset}:${colAsset}`;
                  const v = matrix[key] ?? 0;
                  const bg = rowAsset === colAsset ? '#1e1e1e' : `${corrColor(v)}22`;
                  return (
                    <td key={colAsset} style={{
                      padding: '6px 12px', textAlign: 'center',
                      background: bg, color: rowAsset === colAsset ? t.dim : corrColor(v),
                      border: `1px solid ${t.border}`,
                    }}>
                      {v.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ color: t.dim, fontSize: 10, marginTop: 8 }}>
        Green &lt;0.6 · Amber 0.6–0.8 · Red &gt;0.8 · Updated {new Date(data.updated_at).toLocaleTimeString()}
      </div>
    </div>
  );
}
