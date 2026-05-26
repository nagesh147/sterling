import React from 'react';
import { usePortfolioSummary } from '../hooks/usePortfolioSummary';
import { useMonitorAll } from '../hooks/useMonitorPosition';
import { useLivePnl } from '../hooks/useLivePnl';
import { fmtN } from '../utils/fmt';
import { c as t, tint } from '../styles/terminalUI';

const styles: Record<string, React.CSSProperties> = {
  card: { background: t.raised, border: `1px solid ${t.border}`, borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: t.dim, fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 12 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: t.dim, fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 16, fontWeight: 700, color: t.bright },
  footer: { display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' },
  monitorBtn: {
    background: t.raised, color: t.blue, border: `1px solid ${t.blue}`,
    padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  alertBadge: {
    background: '#cc444422', color: t.red,
    border: `1px solid ${t.red}`, padding: '3px 8px', borderRadius: 3, fontSize: 11,
  },
  partialBadge: {
    background: '#f0c04022', color: t.amber,
    border: `1px solid ${t.amber}`, padding: '3px 8px', borderRadius: 3, fontSize: 11,
  },
};

export function PortfolioSummary() {
  const { data } = usePortfolioSummary();
  const monitor = useMonitorAll();

  const { data: livePnl } = useLivePnl((data?.open_count ?? 0) > 0);

  if (!data) return null;

  const pnlColor = data.total_realized_pnl_usd >= 0 ? t.green : t.red;
  const pnlSign = data.total_realized_pnl_usd >= 0 ? '+' : '';
  const unrealizedPnl = livePnl?.total_estimated_pnl_usd;
  const unrealColor = (unrealizedPnl ?? 0) >= 0 ? t.green : t.red;
  const monitorResult = monitor.data as { exit_recommended?: string[]; partial_recommended?: string[] } | undefined;

  return (
    <div style={styles.card}>
      <div style={styles.title}>PORTFOLIO SUMMARY</div>
      <div style={styles.grid}>
        <div style={styles.cell}>
          <span style={styles.key}>OPEN POSITIONS</span>
          <span style={{ ...styles.val, color: data.open_count > 0 ? t.amber : t.dim }}>
            {data.open_count}
            {data.partially_closed_count > 0 && (
              <span style={{ color: t.amber, fontSize: 11, marginLeft: 4 }}>
                ({data.partially_closed_count}½)
              </span>
            )}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>TOTAL OPEN RISK</span>
          <span style={{ ...styles.val, color: t.red }}>
            ${data.total_open_risk_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>REALIZED P&L</span>
          <span style={{ ...styles.val, color: pnlColor }}>
            {pnlSign}${data.total_realized_pnl_usd.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>UNREALIZED P&L</span>
          <span style={{ ...styles.val, color: unrealColor, fontSize: 14 }}>
            {unrealizedPnl != null
              ? `${unrealizedPnl >= 0 ? '+' : ''}$${fmtN(unrealizedPnl, 0)}`
              : '—'}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>AVG RISK %</span>
          <span style={styles.val}>{data.avg_capital_at_risk_pct.toFixed(2)}%</span>
        </div>
      </div>

      <div style={styles.footer}>
        <button
          style={monitor.isPending ? { ...styles.monitorBtn, opacity: 0.5 } : styles.monitorBtn}
          onClick={() => monitor.mutate()}
          disabled={monitor.isPending || data.open_count === 0}
        >
          {monitor.isPending ? 'CHECKING…' : '⟳ MONITOR ALL'}
        </button>

        {monitorResult?.exit_recommended && monitorResult.exit_recommended.length > 0 && (
          <span style={styles.alertBadge}>
            EXIT: {monitorResult.exit_recommended.join(', ')}
          </span>
        )}
        {monitorResult?.partial_recommended && monitorResult.partial_recommended.length > 0 && (
          <span style={styles.partialBadge}>
            PARTIAL: {monitorResult.partial_recommended.join(', ')}
          </span>
        )}
        {data.underlyings_open.length > 0 && (
          <span style={{ color: t.dim, fontSize: 11 }}>
            Open in: {data.underlyings_open.join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}
