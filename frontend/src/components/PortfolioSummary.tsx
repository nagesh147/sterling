import React from 'react';
import { usePortfolioSummary } from '../hooks/usePortfolioSummary';
import { useMonitorAll } from '../hooks/useMonitorPosition';
import { useLivePnl } from '../hooks/useLivePnl';
import { fmtN } from '../utils/fmt';

const styles: Record<string, React.CSSProperties> = {
  card: { background: '#141414', border: '1px solid #222', borderRadius: 6, padding: 16, marginBottom: 16 },
  title: { color: '#888', fontSize: 11, letterSpacing: 2, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 12 },
  cell: { display: 'flex', flexDirection: 'column', gap: 3 },
  key: { color: '#555', fontSize: 10, letterSpacing: 1 },
  val: { fontSize: 16, fontWeight: 700, color: '#e0e0e0' },
  footer: { display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' },
  monitorBtn: {
    background: '#1a1a2a', color: '#88aaff', border: '1px solid #88aaff',
    padding: '5px 12px', borderRadius: 3, cursor: 'pointer', fontFamily: 'inherit', fontSize: 11,
  },
  alertBadge: {
    background: '#cc444422', color: '#cc4444',
    border: '1px solid #cc4444', padding: '3px 8px', borderRadius: 3, fontSize: 11,
  },
  partialBadge: {
    background: '#f0c04022', color: '#f0c040',
    border: '1px solid #f0c040', padding: '3px 8px', borderRadius: 3, fontSize: 11,
  },
};

export function PortfolioSummary() {
  const { data } = usePortfolioSummary();
  const monitor = useMonitorAll();

  const { data: livePnl } = useLivePnl((data?.open_count ?? 0) > 0);

  if (!data) return null;

  const pnlColor = data.total_realized_pnl_usd >= 0 ? '#44cc88' : '#cc4444';
  const pnlSign = data.total_realized_pnl_usd >= 0 ? '+' : '';
  const unrealizedPnl = livePnl?.total_estimated_pnl_usd;
  const unrealColor = (unrealizedPnl ?? 0) >= 0 ? '#44cc88' : '#cc4444';
  const monitorResult = monitor.data as { exit_recommended?: string[]; partial_recommended?: string[] } | undefined;

  return (
    <div style={styles.card}>
      <div style={styles.title}>PORTFOLIO SUMMARY</div>
      <div style={styles.grid}>
        <div style={styles.cell}>
          <span style={styles.key}>OPEN POSITIONS</span>
          <span style={{ ...styles.val, color: data.open_count > 0 ? '#f0c040' : '#555' }}>
            {data.open_count}
            {data.partially_closed_count > 0 && (
              <span style={{ color: '#f0c040', fontSize: 11, marginLeft: 4 }}>
                ({data.partially_closed_count}½)
              </span>
            )}
          </span>
        </div>
        <div style={styles.cell}>
          <span style={styles.key}>TOTAL OPEN RISK</span>
          <span style={{ ...styles.val, color: '#ff8844' }}>
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
          <span style={{ color: '#444', fontSize: 11 }}>
            Open in: {data.underlyings_open.join(', ')}
          </span>
        )}
      </div>
    </div>
  );
}
