import React from 'react';
import { useWalkForward, useRunWalkForward } from '../hooks/useWalkForward';
import { useSelectedUnderlying } from '../store/useStore';
import { c, gridStyle, tint } from '../styles/terminalUI';

const S: Record<string, React.CSSProperties> = {
  card: { background: c.surface, border: `1px solid ${c.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: c.dim, fontSize: 11, fontWeight: 700, letterSpacing: 2, marginBottom: 12 },
  row: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' as const },
  btn: { background: tint(c.blue, 14), color: c.blue, border: `1px solid ${c.blue}`, padding: '6px 14px', borderRadius: 4, cursor: 'pointer', fontFamily: 'inherit', fontSize: 12 },
  statCard: { background: c.bg, border: `1px solid ${c.border}`, borderRadius: 4, padding: 10 },
  statLabel: { color: c.dim, fontSize: 10, letterSpacing: 1, marginBottom: 4 },
  statVal: { fontSize: 16, fontWeight: 700, color: c.bright },
  grid3: { ...gridStyle(140, 8), marginBottom: 12 },
  stale: { color: c.amber, fontSize: 10 },
  noData: { color: c.dim, fontSize: 12, padding: '16px 0' },
  table: { width: '100%', borderCollapse: 'collapse' as const, fontSize: 11 },
  th: { color: c.dim, fontSize: 10, letterSpacing: 1, padding: '4px 8px', textAlign: 'left' as const, borderBottom: `1px solid ${c.border}` },
  td: { color: c.text, padding: '4px 8px', borderBottom: `1px solid ${c.border}` },
};

function badge(color: string): React.CSSProperties {
  return { background: tint(color), color, border: `1px solid ${tint(color, 40)}`, borderRadius: 3, padding: '2px 10px', fontSize: 12, fontWeight: 700 };
}

function MiniCurve({ curve }: { curve: number[] }) {
  if (curve.length < 2) return null;
  const w = 160, h = 40;
  const min = Math.min(...curve), max = Math.max(...curve);
  const range = max - min || 1;
  const pts = curve.map((v, i) => {
    const x = (i / (curve.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(' ');
  const color = curve[curve.length - 1] >= curve[0] ? c.green : c.red;
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

export function WalkForwardPanel() {
  const underlying = useSelectedUnderlying();
  const { data: cached } = useWalkForward(underlying);
  const { mutate: runWf, isPending: running, data: freshResult, error } = useRunWalkForward();

  const result = freshResult ?? cached;

  return (
    <div style={S.card}>
      <div style={S.title}>WALK-FORWARD ANALYSIS</div>
      <div style={S.row}>
        <button
          style={S.btn}
          disabled={running}
          onClick={() => runWf({ underlying, train_bars: 180, test_bars: 60, step_bars: 30 })}
        >
          {running ? 'Running…' : 'Run Walk-Forward'}
        </button>
        {cached?.run_at && !freshResult && (
          <span style={S.stale}>Last run: {cached.run_at}</span>
        )}
      </div>

      {error && <div style={{ color: c.red, fontSize: 11 }}>{String(error)}</div>}

      {!result && !running && (
        <div style={S.noData}>No results yet — click Run Walk-Forward to analyse {underlying}</div>
      )}

      {result && (
        <>
          <div style={S.row}>
            <span style={badge(c.green)}>OOS Sharpe: {result.aggregate_report?.sharpe?.toFixed(3) ?? '—'}</span>
            <span style={badge(c.blue)}>Rec. Threshold: {result.recommended_threshold?.toFixed(0) ?? '—'}</span>
            <span style={{ color: c.dim, fontSize: 11 }}>{result.windows?.length ?? 0} windows</span>
          </div>

          <div style={S.grid3}>
            {[
              ['Win Rate', result.aggregate_report?.win_rate != null ? `${(result.aggregate_report.win_rate * 100).toFixed(1)}%` : '—'],
              ['Max DD', result.aggregate_report?.max_drawdown != null ? `${(result.aggregate_report.max_drawdown * 100).toFixed(1)}%` : '—'],
              ['Trades', String(result.aggregate_report?.total_trades ?? '—')],
            ].map(([label, val]) => (
              <div key={label} style={S.statCard}>
                <div style={S.statLabel}>{label}</div>
                <div style={S.statVal}>{val}</div>
              </div>
            ))}
          </div>

          {result.oos_equity_curve?.length > 1 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ color: c.dim, fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>OOS EQUITY CURVE</div>
              <MiniCurve curve={result.oos_equity_curve} />
            </div>
          )}

          {result.aggregate_report?.regime_breakdown && Object.keys(result.aggregate_report.regime_breakdown).length > 0 && (
            <div>
              <div style={{ color: c.dim, fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>REGIME BREAKDOWN</div>
              <table style={S.table}>
                <thead>
                  <tr>
                    <th style={S.th}>Regime</th>
                    <th style={S.th}>Trades</th>
                    <th style={S.th}>Win Rate</th>
                    <th style={S.th}>Sharpe Proxy</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.aggregate_report.regime_breakdown).map(([regime, stats]) => (
                    <tr key={regime}>
                      <td style={S.td}>{regime}</td>
                      <td style={S.td}>{stats.trade_count}</td>
                      <td style={{ ...S.td, color: stats.win_rate >= 0.5 ? c.green : c.red }}>
                        {(stats.win_rate * 100).toFixed(1)}%
                      </td>
                      <td style={S.td}>{stats.sharpe_proxy.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
